from flask import Flask
from ..blockchain.blockchain import Blockchain
from ..network.node import NetworkNode
from ..social.network_map import NetworkMap
from ..social.request import SocialRequest


class AppState:
    def __init__(self):
        self.blockchain = Blockchain()
        self.network_node = NetworkNode()
        self.network_map = NetworkMap()
        self.agent_registry = {}  # did -> AIAgent
        self.social_requests = {}  # request_id -> SocialRequest


app_state = AppState()


def create_app(state: AppState = None) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = False

    if state is None:
        state = app_state

    app.app_state = state

    from .routes.chain import chain_bp
    from .routes.network import network_bp
    from .routes.social import social_bp
    from .routes.agents import agents_bp

    app.register_blueprint(chain_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(agents_bp)

    return app
