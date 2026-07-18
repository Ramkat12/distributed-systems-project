"""Tests for the load balancer's Flask endpoints (load_balancer/lb.py).

All Docker CLI calls (`subprocess.run`) and downstream server requests
(`requests.get`) are mocked, so these tests run without Docker installed
or any containers actually running.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "load_balancer"))

import lb  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state():
    """lb.py keeps its registry in module-level globals; reset them
    between tests so each test starts from an empty ring."""
    lb.servers.clear()
    lb.chmap.hash_map = [None] * lb.chmap.num_slots
    lb.server_id_counter = 1
    yield


@pytest.fixture
def client():
    lb.app.config["TESTING"] = True
    return lb.app.test_client()


def test_rep_reports_empty_ring(client):
    resp = client.get("/rep")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["message"]["N"] == 0
    assert data["message"]["replicas"] == []


@patch("lb.subprocess.run")
def test_add_spawns_requested_number_of_servers(mock_run, client):
    mock_run.return_value = MagicMock(returncode=0)
    resp = client.post("/add", json={"n": 2})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["message"]["N"] == 2
    assert mock_run.call_count == 2


@patch("lb.subprocess.run")
def test_add_rejects_mismatched_hostname_count(mock_run, client):
    resp = client.post("/add", json={"n": 1, "hostnames": ["a", "b"]})
    assert resp.status_code == 400
    mock_run.assert_not_called()


@patch("lb.subprocess.run")
def test_rm_removes_specific_hostname(mock_run, client):
    mock_run.return_value = MagicMock(returncode=0)
    client.post("/add", json={"n": 3, "hostnames": ["s1", "s2", "s3"]})

    resp = client.delete("/rm", json={"n": 1, "hostnames": ["s2"]})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["message"]["N"] == 2
    assert "s2" not in data["message"]["replicas"]


@patch("lb.subprocess.run")
def test_rm_rejects_mismatched_hostname_count(mock_run, client):
    resp = client.delete("/rm", json={"n": 1, "hostnames": ["a", "b"]})
    assert resp.status_code == 400


def test_route_returns_503_when_no_servers_registered(client):
    resp = client.get("/home")
    assert resp.status_code == 503


@patch("lb.req.get")
@patch("lb.subprocess.run")
def test_route_forwards_to_selected_server(mock_run, mock_get, client):
    mock_run.return_value = MagicMock(returncode=0)
    client.post("/add", json={"n": 1, "hostnames": ["s1"]})

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": "Hello from Server: 1", "status": "successful"}
    mock_get.return_value = mock_response

    resp = client.get("/home")
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Hello from Server: 1"


@patch("lb.req.get")
@patch("lb.subprocess.run")
def test_route_returns_400_when_downstream_404s(mock_run, mock_get, client):
    mock_run.return_value = MagicMock(returncode=0)
    client.post("/add", json={"n": 1, "hostnames": ["s1"]})

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    resp = client.get("/does-not-exist")
    assert resp.status_code == 400


@patch("lb.req.get", side_effect=Exception("connection refused"))
@patch("lb.subprocess.run")
def test_route_returns_503_when_server_unreachable(mock_run, mock_get, client):
    mock_run.return_value = MagicMock(returncode=0)
    client.post("/add", json={"n": 1, "hostnames": ["s1"]})

    resp = client.get("/home")
    assert resp.status_code == 503
