from flask import Blueprint, render_template, session, redirect, url_for, current_app
from .auth import login_required

web_bp = Blueprint("web", __name__)


@web_bp.route("/")
def index():
    """Public landing page when not logged in; dashboard when logged in."""
    if "user_did" in session:
        state = current_app.app_state
        chain_data = state.blockchain.to_dict()
        return render_template(
            "dashboard.html",
            chain=chain_data,
            username=session.get("username"),
            user_did=session.get("user_did"),
        )
    return render_template("landing.html")


@web_bp.route("/dashboard")
@login_required
def dashboard():
    state = current_app.app_state
    chain_data = state.blockchain.to_dict()
    return render_template(
        "dashboard.html",
        chain=chain_data,
        username=session.get("username"),
        user_did=session.get("user_did"),
    )


@web_bp.route("/profile")
@web_bp.route("/profile/<path:did>")
@login_required
def profile(did=None):
    state = current_app.app_state
    if did is None:
        did = session.get("user_did")
    profile_obj = state.network_map.get_profile(did)
    connections = state.network_map.get_connections(did)
    conn_profiles = [state.network_map.get_profile(c) for c in connections if state.network_map.get_profile(c)]
    return render_template("profile.html", profile=profile_obj, connections=conn_profiles, did=did, username=session.get("username"), user_did=session.get("user_did"), agent_type=session.get("agent_type"))


@web_bp.route("/network")
@login_required
def network():
    state = current_app.app_state
    return render_template("network.html", username=session.get("username"), user_did=session.get("user_did"))


@web_bp.route("/my-network")
@login_required
def my_network():
    """Full-page 3D interactive network visualization for the logged-in user."""
    return render_template("user_network.html", username=session.get("username"), user_did=session.get("user_did"))
