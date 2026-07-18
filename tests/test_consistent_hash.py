"""Tests for the consistent hashing ring (load_balancer/consistent_hash.py).

Uses a small ring (num_slots=4, num_virtual=2) so slot placement and
collisions can be verified by hand against Phi(i,j) and H(i).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "load_balancer"))

from consistent_hash import ConsistentHashMap


def test_empty_ring_returns_none():
    chmap = ConsistentHashMap(num_slots=4, num_virtual=2)
    assert chmap.get_server(0) is None


def test_add_server_places_virtual_nodes():
    chmap = ConsistentHashMap(num_slots=4, num_virtual=2)
    chmap.add_server(1)
    # Phi(1,0)=26%4=2, Phi(1,1)=29%4=1
    assert chmap.hash_map == [None, 1, 1, None]


def test_collision_resolved_by_linear_probing():
    chmap = ConsistentHashMap(num_slots=4, num_virtual=2)
    chmap.add_server(1)
    chmap.add_server(2)
    # Phi(2,0)=29%4=1 (taken) -> probes to slot 3
    # Phi(2,1)=32%4=0 (free)
    assert chmap.hash_map == [2, 1, 1, 2]


def test_get_server_routes_clockwise():
    chmap = ConsistentHashMap(num_slots=4, num_virtual=2)
    chmap.add_server(1)
    chmap.add_server(2)
    assert chmap.get_server(0) == 1
    assert chmap.get_server(1) == 2
    assert chmap.get_server(2) == 1
    assert chmap.get_server(3) == 2


def test_remove_server_clears_only_its_own_slots():
    chmap = ConsistentHashMap(num_slots=4, num_virtual=2)
    chmap.add_server(1)
    chmap.add_server(2)
    chmap.remove_server(1)
    assert chmap.hash_map == [2, None, None, 2]


def test_get_server_walks_past_removed_slot():
    chmap = ConsistentHashMap(num_slots=4, num_virtual=2)
    chmap.add_server(1)
    chmap.add_server(2)
    chmap.remove_server(1)
    # req_id 0 hashes to slot 1, now empty -> walks to slot 3 (server 2)
    assert chmap.get_server(0) == 2


def test_get_server_is_deterministic_for_same_ring_state():
    chmap = ConsistentHashMap(num_slots=512, num_virtual=9)
    chmap.add_server(1)
    chmap.add_server(2)
    chmap.add_server(3)
    first_pass = [chmap.get_server(req_id) for req_id in range(1000)]
    second_pass = [chmap.get_server(req_id) for req_id in range(1000)]
    assert first_pass == second_pass
