import pytest
from socialchain.network import PeerRegistry, NetworkNode


def test_peer_registry_add():
    registry = PeerRegistry()
    registry.add("did:socialchain:abc", "127.0.0.1:5001")
    assert len(registry) == 1
    assert registry.get("did:socialchain:abc") == "127.0.0.1:5001"


def test_peer_registry_remove():
    registry = PeerRegistry()
    registry.add("did:socialchain:abc", "127.0.0.1:5001")
    result = registry.remove("did:socialchain:abc")
    assert result is True
    assert len(registry) == 0


def test_peer_registry_remove_nonexistent():
    registry = PeerRegistry()
    result = registry.remove("did:socialchain:notexist")
    assert result is False


def test_peer_registry_list():
    registry = PeerRegistry()
    registry.add("did:socialchain:abc", "127.0.0.1:5001")
    registry.add("did:socialchain:def", "127.0.0.1:5002")
    peers = registry.list()
    assert len(peers) == 2
    assert "did:socialchain:abc" in peers


def test_network_node_creation():
    node = NetworkNode(host="127.0.0.1", port=5000)
    assert node.host == "127.0.0.1"
    assert node.port == 5000
    assert node.node_id.startswith("did:socialchain:")


def test_network_node_register_peer():
    node = NetworkNode()
    node.register_peer("did:socialchain:peer1", "192.168.1.1:5001")
    peers = node.get_peers()
    assert "did:socialchain:peer1" in peers
    assert peers["did:socialchain:peer1"] == "192.168.1.1:5001"


def test_network_node_remove_peer():
    node = NetworkNode()
    node.register_peer("did:socialchain:peer1", "192.168.1.1:5001")
    result = node.remove_peer("did:socialchain:peer1")
    assert result is True
    assert "did:socialchain:peer1" not in node.get_peers()
