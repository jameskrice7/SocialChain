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
