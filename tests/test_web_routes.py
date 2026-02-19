"""Tests for the new web routes: landing page and 3D user network."""
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


def _login(client, app, state):
    """Register and log in a test user, return the test client with session."""
    from socialchain.api.auth import create_user
    from socialchain.social.profile import Profile, DeviceType

    user = create_user("testuser", "testpass", "human")
    state.user_registry["testuser"] = user
    state.did_to_username[user.did] = "testuser"
    profile = Profile(did=user.did, display_name="testuser", device_type=DeviceType.HUMAN)
    state.network_map.add_profile(profile)

    with client.session_transaction() as sess:
        sess["user_did"] = user.did
        sess["username"] = "testuser"
        sess["agent_type"] = "human"
    return user


def test_landing_page_unauthenticated(client):
    """GET / for an unauthenticated user should return the landing page."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()
    assert "SocialChain" in html
    # Landing page has the tab navigation
    assert "Overview" in html
    assert "Aims" in html
    assert "Functionality" in html
    assert "Technology" in html


def test_landing_page_authenticated_shows_dashboard(client, app, state):
    """GET / for a logged-in user should return the dashboard."""
    _login(client, app, state)
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Dashboard" in html


def test_dashboard_route_requires_login(client):
    """GET /dashboard without a session should redirect to login."""
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_route_authenticated(client, app, state):
    """GET /dashboard with a session should return the dashboard page."""
    _login(client, app, state)
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Dashboard" in html


def test_my_network_requires_login(client):
    """GET /my-network without a session should redirect to login."""
    response = client.get("/my-network")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_my_network_authenticated(client, app, state):
    """GET /my-network with a session should return the 3D network page."""
    _login(client, app, state)
    response = client.get("/my-network")
    assert response.status_code == 200
    html = response.data.decode()
    # Should contain key 3D network elements
    assert "3D" in html or "ForceGraph3D" in html or "My 3D Network" in html


def test_ide_requires_login(client):
    """GET /ide without a session should redirect to login."""
    response = client.get("/ide")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_ide_authenticated(client, app, state):
    """GET /ide with a session should return the Network Workbench page."""
    _login(client, app, state)
    response = client.get("/ide")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Node Registry" in html
    assert "Topology Builder" in html
    assert "Transaction Inspector" in html
    assert "Contract Editor" in html


def test_workbench_shell_authenticated(client, app, state):
    """Authenticated pages should include the VS Code workbench shell elements."""
    _login(client, app, state)
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.data.decode()
    assert "sc-activity-bar" in html
    assert "sc-chat-panel" in html
    assert "sc-statusbar" in html
    assert "Agent Assistant" in html


def test_agent_chat_endpoint(client, app, state):
    """POST /api/agents/chat should return an agent reply."""
    response = client.post(
        "/api/agents/chat",
        json={"message": "Hello"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "reply" in data
    assert "agent" in data
    assert len(data["reply"]) > 0


def test_agent_chat_requires_message(client):
    """POST /api/agents/chat without a message should return 400."""
    response = client.post(
        "/api/agents/chat",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_agent_feed_endpoint(client, app, state):
    """GET /api/agents/feed should return an activity feed (possibly empty)."""
    response = client.get("/api/agents/feed")
    assert response.status_code == 200
    data = response.get_json()
    assert "feed" in data
    assert isinstance(data["feed"], list)
