# Load Balancer

A simulated distributed load balancer using Docker containers and consistent hashing to spread requests across dynamically managed backend server replicas. The load balancer can add/remove servers on demand and automatically detects and replaces dead ones.

## Architecture

```
client → load_balancer:5000 → (consistent hash ring) → Server_1 / Server_2 / Server_3 ...
                ↑                                              │
                └────────── heartbeat check every 5s ──────────┘
                         (dead servers auto-replaced)
```

- **`server/`** — the backend. A minimal Flask app ([server.py](server/server.py)) with two routes:
  - `GET /home` — returns a greeting identifying itself by `SERVER_ID`
  - `GET /heartbeat` — health check, always returns 200

  This is built once into a `server_img` Docker image. The load balancer spawns/kills containers from this image as needed.

- **`load_balancer/`** — the brain ([lb.py](load_balancer/lb.py)). A Flask app that:
  - Spawns `N` server containers on startup (via the Docker CLI, using the host's Docker socket) and registers them on a consistent-hash ring.
  - Runs a background thread every 5s that pings each server's `/heartbeat`; any that fail are killed and replaced automatically (self-healing).
  - Exposes these endpoints:
    - `GET /rep` — list current server replicas
    - `POST /add` — spin up more server containers, e.g. `{"n": 2}`
    - `DELETE /rm` — tear down server containers, e.g. `{"n": 1}`
    - `GET /<path>` — routes the request: hashes a random request ID onto the ring, finds the nearest server, proxies the request there, and returns the result

  The load balancer container has Docker installed inside it and mounts `/var/run/docker.sock`, so it can spawn/kill sibling containers as if it were the host.

- **`load_balancer/consistent_hash.py`** — the consistent hashing ring. 512 slots, 9 virtual nodes per server (placed via a hash function `Φ`, with linear probing on collisions). Incoming requests are hashed via `H` and routed clockwise to the nearest server slot. This gives even distribution and avoids remapping everything when servers are added/removed.

- **`analysis/`** — benchmarking scripts ([analyze.py](analysis/analyze.py)), not part of the running system. Fires thousands of requests at the load balancer and plots:
  - `a1` — request distribution across servers for N=3
  - `a2` — scalability as N varies from 2 to 6
  - `a3` — failure/recovery time after killing a container
  - `a4` — offline comparison of two different hash function choices

## Running it

Requires Docker Desktop running.

```bash
make build   
make up      
```

Test it:

```bash
curl http://localhost:5000/rep
curl http://localhost:5000/home
```

Scale up/down:

```bash
curl -X POST http://localhost:5000/add -H "Content-Type: application/json" -d '{"n": 2}'
curl -X DELETE http://localhost:5000/rm -H "Content-Type: application/json" -d '{"n": 1}'
```

Stop:

```bash
make down    
make clean   
```

## Running the analysis

```bash
pip install -r analysis/requirements.txt
python analysis/analyze.py all   
```

The load balancer must already be running at `localhost:5000` for `a1`–`a3` (`a4` is a pure offline simulation).
