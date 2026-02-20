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


# ── New functionality tests ──────────────────────────────────────────────────

def test_social_links_now_supports_twitter(client):
    """PATCH /api/social/profiles/<did>/social-links should accept twitter."""
    # Create a profile
    did = "did:socialchain:twittertest"
    client.post("/api/social/profiles", json={"did": did, "display_name": "Twitter Tester"})
    # Update with twitter link
    resp = client.patch(
        f"/api/social/profiles/{did}/social-links",
        json={"social_links": {"twitter": "https://x.com/testhandle"}},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "twitter" in data["social_links"]
    assert data["social_links"]["twitter"] == "https://x.com/testhandle"


def test_social_links_rejects_invalid_platform(client):
    """PATCH social-links should reject unknown platform keys."""
    did = "did:socialchain:badplatform"
    client.post("/api/social/profiles", json={"did": did, "display_name": "Bad"})
    resp = client.patch(
        f"/api/social/profiles/{did}/social-links",
        json={"social_links": {"tiktok": "https://tiktok.com/test"}},
    )
    # Unknown key is silently ignored; no error
    assert resp.status_code == 200


def test_iot_device_registration(client):
    """POST /api/social/profiles/<did>/iot-devices should register a device."""
    did = "did:socialchain:iotowner"
    client.post("/api/social/profiles", json={"did": did, "display_name": "IoT Owner"})
    resp = client.post(
        f"/api/social/profiles/{did}/iot-devices",
        json={"name": "Temp Sensor", "type": "sensor", "location": "Living Room", "status": "online"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["device"]["name"] == "Temp Sensor"
    assert data["device"]["type"] == "sensor"


def test_iot_device_invalid_type(client):
    """POST iot-devices with invalid type should return 400."""
    did = "did:socialchain:iotowner2"
    client.post("/api/social/profiles", json={"did": did, "display_name": "IoT Owner 2"})
    resp = client.post(
        f"/api/social/profiles/{did}/iot-devices",
        json={"name": "Widget", "type": "invalidtype"},
    )
    assert resp.status_code == 400


def test_iot_device_missing_name(client):
    """POST iot-devices without a name should return 400."""
    did = "did:socialchain:iotowner3"
    client.post("/api/social/profiles", json={"did": did, "display_name": "IoT Owner 3"})
    resp = client.post(
        f"/api/social/profiles/{did}/iot-devices",
        json={"type": "sensor"},
    )
    assert resp.status_code == 400


def test_register_with_display_name_and_bio(client, app, state):
    """POST /register with display_name and bio should populate profile metadata."""
    resp = client.post("/register", data={
        "username": "biouser",
        "display_name": "Bio User Display",
        "bio": "I am a test node on the SocialChain network.",
        "password": "pass123",
        "confirm_password": "pass123",
        "agent_type": "human",
    }, follow_redirects=False)
    # Should redirect to dashboard on success
    assert resp.status_code == 302
    # Check profile was created with bio and display_name
    profile = state.network_map.get_profile(state.user_registry["biouser"].did)
    assert profile is not None
    assert profile.display_name == "Bio User Display"
    assert profile.metadata.get("bio") == "I am a test node on the SocialChain network."


def test_register_with_social_links(client, app, state):
    """POST /register with social links should populate profile metadata.social_links."""
    resp = client.post("/register", data={
        "username": "socialreguser",
        "password": "pass123",
        "confirm_password": "pass123",
        "agent_type": "human",
        "sl_facebook": "https://facebook.com/socialreguser",
        "sl_twitter": "https://x.com/socialreguser",
    }, follow_redirects=False)
    assert resp.status_code == 302
    profile = state.network_map.get_profile(state.user_registry["socialreguser"].did)
    assert profile is not None
    social_links = profile.metadata.get("social_links", {})
    assert social_links.get("facebook") == "https://facebook.com/socialreguser"
    assert social_links.get("twitter") == "https://x.com/socialreguser"


def test_login_page_has_remember_me(client):
    """GET /login should include a remember_me checkbox."""
    resp = client.get("/login")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "remember_me" in html or "remember" in html.lower()


def test_login_page_has_download_link(client):
    """GET /login should include a link to download the app."""
    resp = client.get("/login")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "releases" in html or "Download" in html
