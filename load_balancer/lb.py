"""Load balancer service.

Spawns/kills backend server containers via the Docker CLI (using the
host's Docker socket mounted into this container), registers them on a
consistent-hash ring, forwards client requests to the ring-selected
replica, and runs a background heartbeat thread that detects and
replaces dead replicas automatically.
"""
from flask import Flask, jsonify, request
import os, threading, time, random, string, subprocess
import requests as req

from consistent_hash import ConsistentHashMap

app = Flask(__name__)

N             = int(os.environ.get("N", 3))
SERVER_IMAGE  = "server_img"
NETWORK       = os.environ.get("NETWORK", "net1")

chmap          = ConsistentHashMap()
servers        = {}        # hostname: numeric server_id
server_id_counter = 1
lock           = threading.Lock()

# helpers 

def random_hostname():
    """Generate a random container/hostname like 'Server_A1B2'."""
    return "Server_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))

def spawn_container(hostname, server_id):
    """Start a new server container on the shared Docker network via the
    Docker CLI. Returns True on success."""
    result = subprocess.run(
        ['docker', 'run', '--name', hostname,
         '--network', NETWORK, '--network-alias', hostname,
         '-e', f'SERVER_ID={server_id}', '-d', f'{SERVER_IMAGE}:latest'],
        capture_output=True, text=True
    )
    return result.returncode == 0

def kill_container(hostname):
    """Stop and remove a server container via the Docker CLI."""
    subprocess.run(['docker', 'stop', hostname], capture_output=True)
    subprocess.run(['docker', 'rm',   hostname], capture_output=True)

def add_server_internal(hostname, server_id):
    """Spawn container + register in ring. Caller must hold lock."""
    if spawn_container(hostname, server_id):
        servers[hostname] = server_id
        chmap.add_server(server_id)
        return True
    return False

def remove_server_internal(hostname):
    """Remove from ring + kill container. Caller must hold lock."""
    server_id = servers.pop(hostname, None)
    if server_id is not None:
        chmap.remove_server(server_id)
        kill_container(hostname)

# startup 

def init_servers():
    """Spawn the initial N server containers at startup and register
    them on the hash ring."""
    global server_id_counter
    with lock:
        for i in range(1, N + 1):
            hostname = f"Server_{i}"
            add_server_internal(hostname, server_id_counter)
            server_id_counter += 1

# heartbeat monitor 

def heartbeat_loop():
    """Background thread: every 5s, ping every registered server's
    /heartbeat endpoint and replace any that fail to respond with a
    freshly spawned container (self-healing)."""
    global server_id_counter
    while True:
        time.sleep(5)

        # Snapshot hostnames without holding the lock during I/O
        with lock:
            snapshot = list(servers.keys())

        dead = []
        for hostname in snapshot:
            try:
                r = req.get(f"http://{hostname}:5000/heartbeat", timeout=2)
                if r.status_code != 200:
                    dead.append(hostname)
            except Exception:
                dead.append(hostname)

        for hostname in dead:
            print(f"[LB] {hostname} is dead, respawning...")

            # Remove from ring state under lock (fast), grab new ID atomically
            with lock:
                sid = servers.pop(hostname, None)
                if sid is None:
                    continue   # already removed by a concurrent /rm
                chmap.remove_server(sid)
                new_id = server_id_counter
                server_id_counter += 1

            new_name = random_hostname()

            # Docker ops happen outside the lock so requests are never blocked
            kill_container(hostname)
            if spawn_container(new_name, new_id):
                with lock:
                    servers[new_name] = new_id
                    chmap.add_server(new_id)
            else:
                print(f"[LB] Failed to spawn replacement for {hostname}")

# endpoints 

@app.route("/rep", methods=["GET"])
def rep():
    """Return the current replica count and hostnames."""
    with lock:
        return jsonify({
            "message": {"N": len(servers), "replicas": list(servers.keys())},
            "status": "successful"
        }), 200


@app.route("/add", methods=["POST"])
def add():
    """Scale up: spawn `n` new server containers (using any given
    `hostnames`, filling the rest with random ones) and register them
    on the ring."""
    global server_id_counter
    data      = request.json
    n         = data.get("n", 0)
    hostnames = list(data.get("hostnames", []))

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400

    while len(hostnames) < n:
        hostnames.append(random_hostname())

    with lock:
        for hostname in hostnames:
            add_server_internal(hostname, server_id_counter)
            server_id_counter += 1
        return jsonify({
            "message": {"N": len(servers), "replicas": list(servers.keys())},
            "status": "successful"
        }), 200


@app.route("/rm", methods=["DELETE"])
def remove():
    """Scale down: remove `n` server containers (specific `hostnames`
    if given, otherwise chosen at random) from the ring and tear them
    down."""
    data      = request.json
    n         = data.get("n", 0)
    hostnames = list(data.get("hostnames", []))

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400

    with lock:
        remaining  = n - len(hostnames)
        candidates = [h for h in servers if h not in hostnames]
        hostnames += random.sample(candidates, min(remaining, len(candidates)))

        for hostname in hostnames:
            if hostname in servers:
                remove_server_internal(hostname)

        return jsonify({
            "message": {"N": len(servers), "replicas": list(servers.keys())},
            "status": "successful"
        }), 200


@app.route("/<path:path>", methods=["GET"])
def route(path):
    """Forward an arbitrary GET request to whichever server the
    consistent-hash ring selects for a freshly generated random
    request ID."""
    req_id = random.randint(100000, 999999)
    with lock:
        server_id = chmap.get_server(req_id)
        target    = next((h for h, sid in servers.items() if sid == server_id), None)

    if target is None:
        return jsonify({
            "message": "<Error> No servers available",
            "status": "failure"
        }), 503

    try:
        r = req.get(f"http://{target}:5000/{path}", timeout=5)
        if r.status_code == 404:
            return jsonify({
                "message": f"<Error> '/{path}' endpoint does not exist in server replicas",
                "status": "failure"
            }), 400
        return jsonify(r.json()), r.status_code
    except Exception:
        return jsonify({
            "message": f"<Error> Server '{target}' is unavailable",
            "status": "failure"
        }), 503


if __name__ == "__main__":
    init_servers()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
