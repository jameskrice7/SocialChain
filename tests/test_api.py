import json
import pytest
from socialchain.api.app import create_app, AppState


@pytest.fixture
def state():
    return AppState()


@pytest.fixture
def app(state):
    application = create_app(state=state)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_get_chain(client):
    response = client.get("/api/chain")
    assert response.status_code == 200
    data = response.get_json()
    assert "chain" in data
    assert data["length"] == 1  # genesis block


def test_create_transaction(client):
    payload = {"sender": "did:sc:alice", "recipient": "did:sc:bob", "data": {"amount": 5}}
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert "tx_id" in data


def test_mine_block(client):
    # Add a transaction first
    payload = {"sender": "did:sc:alice", "recipient": "did:sc:bob", "data": {"amount": 5}}
    client.post("/api/transactions", json=payload)
    # Mine
    response = client.post("/api/mine", json={"miner_did": "did:sc:miner"})
    assert response.status_code == 200
    data = response.get_json()
    assert "block" in data


def test_mine_no_transactions(client):
    response = client.post("/api/mine", json={})
    assert response.status_code == 400


def test_list_peers(client):
    response = client.get("/api/network/peers")
    assert response.status_code == 200
    data = response.get_json()
    assert "peers" in data


def test_register_peer(client):
    payload = {"did": "did:sc:peer1", "address": "127.0.0.1:5001"}
    response = client.post("/api/network/peers", json=payload)
    assert response.status_code == 201


def test_list_profiles(client):
    response = client.get("/api/social/profiles")
    assert response.status_code == 200
    data = response.get_json()
    assert "profiles" in data


def test_create_profile(client):
    payload = {"did": "did:sc:alice", "display_name": "Alice", "device_type": "human"}
    response = client.post("/api/social/profiles", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["profile"]["display_name"] == "Alice"


def test_get_network_map(client):
    response = client.get("/api/social/map")
    assert response.status_code == 200
    data = response.get_json()
    assert "map" in data


def test_create_social_request(client):
    payload = {
        "requester_did": "did:sc:alice",
        "target_did": "did:sc:bob",
        "action": "SEND_MESSAGE",
        "payload": {"message": "Hi!"},
    }
    response = client.post("/api/social/requests", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["request"]["status"] == "PENDING"


def test_list_social_requests(client):
    response = client.get("/api/social/requests")
    assert response.status_code == 200
    data = response.get_json()
    assert "requests" in data


def test_update_social_request(client):
    # Create a request first
    payload = {
        "requester_did": "did:sc:alice",
        "target_did": "did:sc:bob",
        "action": "REQUEST_FEATURE",
    }
    create_resp = client.post("/api/social/requests", json=payload)
    request_id = create_resp.get_json()["request"]["request_id"]
    # Update it
    response = client.patch(f"/api/social/requests/{request_id}", json={"status": "APPROVED"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["request"]["status"] == "APPROVED"


def test_list_agents(client):
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.get_json()
    assert "agents" in data


def test_register_agent(client):
    payload = {"name": "MyAgent", "capabilities": ["echo"]}
    response = client.post("/api/agents", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["agent"]["name"] == "MyAgent"


def test_submit_task_to_agent(client):
    # Register agent
    reg_resp = client.post("/api/agents", json={"name": "TaskAgent", "capabilities": ["echo"]})
    agent_did = reg_resp.get_json()["agent"]["did"]
    # Submit task - need to URL-encode the DID
    from urllib.parse import quote
    encoded_did = quote(agent_did, safe="")
    response = client.post(
        f"/api/agents/{encoded_did}/tasks",
        json={"description": "Echo test", "payload": {"capability": "echo"}},
    )
    assert response.status_code == 201


def test_list_agent_tasks(client):
    reg_resp = client.post("/api/agents", json={"name": "TaskAgent2", "capabilities": ["echo"]})
    agent_did = reg_resp.get_json()["agent"]["did"]
    from urllib.parse import quote
    encoded_did = quote(agent_did, safe="")
    response = client.get(f"/api/agents/{encoded_did}/tasks")
    assert response.status_code == 200
    data = response.get_json()
    assert "tasks" in data
