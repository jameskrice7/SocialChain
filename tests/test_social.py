import pytest
from socialchain.social import Profile, DeviceType, NetworkMap, SocialRequest, RequestAction, RequestStatus


def test_profile_creation():
    p = Profile(did="did:socialchain:abc", display_name="Alice", device_type=DeviceType.HUMAN)
    assert p.did == "did:socialchain:abc"
    assert p.display_name == "Alice"
    assert p.device_type == DeviceType.HUMAN


def test_profile_to_dict():
    p = Profile(did="did:socialchain:abc", display_name="Alice", device_type=DeviceType.HUMAN, metadata={"bio": "hello"})
    d = p.to_dict()
    assert d["did"] == "did:socialchain:abc"
    assert d["display_name"] == "Alice"
    assert d["device_type"] == "human"
    assert d["metadata"]["bio"] == "hello"


def test_profile_from_dict():
    d = {"did": "did:socialchain:abc", "display_name": "Alice", "device_type": "agent", "metadata": {}}
    p = Profile.from_dict(d)
    assert p.did == "did:socialchain:abc"
    assert p.device_type == DeviceType.AGENT


def test_network_map_add_profile():
    nm = NetworkMap()
    p = Profile(did="did:socialchain:alice", display_name="Alice")
    nm.add_profile(p)
    assert nm.get_profile("did:socialchain:alice") is not None


def test_network_map_visualize():
    nm = NetworkMap()
    p1 = Profile(did="did:socialchain:alice", display_name="Alice")
    p2 = Profile(did="did:socialchain:bob", display_name="Bob")
    nm.add_profile(p1)
    nm.add_profile(p2)
    nm.add_connection("did:socialchain:alice", "did:socialchain:bob")
    adj = nm.visualize()
    assert "did:socialchain:alice" in adj
    assert "did:socialchain:bob" in adj["did:socialchain:alice"]


def test_network_map_connections():
    nm = NetworkMap()
    p1 = Profile(did="did:socialchain:alice", display_name="Alice")
    p2 = Profile(did="did:socialchain:bob", display_name="Bob")
    nm.add_profile(p1)
    nm.add_profile(p2)
    nm.add_connection("did:socialchain:alice", "did:socialchain:bob")
    conns = nm.get_connections("did:socialchain:alice")
    assert "did:socialchain:bob" in conns


def test_social_request_creation():
    req = SocialRequest(
        requester_did="did:socialchain:alice",
        target_did="did:socialchain:bob",
        action=RequestAction.SEND_MESSAGE,
        payload={"message": "Hello!"},
    )
    assert req.requester_did == "did:socialchain:alice"
    assert req.action == RequestAction.SEND_MESSAGE
    assert req.status == RequestStatus.PENDING
    assert req.request_id is not None


def test_social_request_to_dict():
    req = SocialRequest(
        requester_did="did:socialchain:alice",
        target_did="did:socialchain:bob",
        action=RequestAction.REQUEST_FEATURE,
    )
    d = req.to_dict()
    assert d["action"] == "REQUEST_FEATURE"
    assert d["status"] == "PENDING"


def test_social_request_from_dict():
    req = SocialRequest(
        requester_did="did:socialchain:alice",
        target_did="did:socialchain:bob",
        action=RequestAction.DEPLOY_AGENT,
    )
    d = req.to_dict()
    req2 = SocialRequest.from_dict(d)
    assert req2.request_id == req.request_id
    assert req2.action == RequestAction.DEPLOY_AGENT
