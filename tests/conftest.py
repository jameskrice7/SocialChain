import pytest
from socialchain.api.app import create_app, AppState


@pytest.fixture
def app_state():
    return AppState()


@pytest.fixture
def app(app_state):
    application = create_app(state=app_state)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
