"""Tests for the backend server replica (server/server.py)."""
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


def test_home_reports_configured_server_id(monkeypatch):
    monkeypatch.setenv("SERVER_ID", "42")
    import server as server_module
    importlib.reload(server_module)  # SERVER_ID is read at import time
    client = server_module.app.test_client()

    resp = client.get("/home")
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Hello from Server: 42"


def test_heartbeat_always_returns_200(monkeypatch):
    monkeypatch.setenv("SERVER_ID", "42")
    import server as server_module
    importlib.reload(server_module)
    client = server_module.app.test_client()

    resp = client.get("/heartbeat")
    assert resp.status_code == 200
