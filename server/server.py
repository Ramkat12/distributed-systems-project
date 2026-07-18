"""Backend server replica.

A minimal Flask app representing one backend replica. Its SERVER_ID is
injected by the load balancer when the container is spawned, so its
/home response identifies which replica handled the request.
"""
from flask import Flask, jsonify
import os

app = Flask(__name__)

SERVER_ID = os.environ.get("SERVER_ID", "Unknown")

@app.route("/home", methods=["GET"])
def home():
    """Identify this replica -- used by the load balancer's demo route."""
    return jsonify({
        "message": f"Hello from Server: {SERVER_ID}",
        "status": "successful"
    }), 200

@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    """Health check polled by the load balancer's heartbeat thread."""
    return "", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)