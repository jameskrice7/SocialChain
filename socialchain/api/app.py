import os
import secrets
from flask import Flask
from ..blockchain.blockchain import Blockchain
from ..network.node import NetworkNode
from ..social.network_map import NetworkMap
from ..social.request import SocialRequest
from .auth import User


class AppState:
    def __init__(self):
        self.blockchain = Blockchain()
        self.network_node = NetworkNode()
        self.network_map = NetworkMap()
        self.agent_registry = {}  # did -> AIAgent
        self.social_requests = {}  # request_id -> SocialRequest
        self.user_registry = {}  # username -> User
        self.did_to_username = {}  # did -> username


app_state = AppState()


def create_app(state: AppState = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["TESTING"] = False
    app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

    if state is None:
        state = app_state

    app.app_state = state

    from .routes.chain import chain_bp
    from .routes.network import network_bp
    from .routes.social import social_bp
    from .routes.agents import agents_bp
    from .routes.auth import auth_bp
    from .routes.web import web_bp

    app.register_blueprint(chain_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)

    return app
