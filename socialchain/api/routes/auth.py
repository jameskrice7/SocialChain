from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
import time
from ..auth import create_user
from ...social.profile import Profile, DeviceType
from ...blockchain.transaction import Transaction

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_did" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_did" in session:
        return redirect(url_for("web.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        state = current_app.app_state
        user = state.user_registry.get(username)
        if user and user.check_password(password):
            session["user_did"] = user.did
            session["username"] = user.username
            session["agent_type"] = user.agent_type
            # Record login status on blockchain
            tx = Transaction(
                sender=user.did,
                recipient="NETWORK",
                data={"type": "status_update", "status": "online", "timestamp": time.time()},
            )
            state.blockchain.add_transaction(tx)
            profile = state.network_map.get_profile(user.did)
            if profile:
                profile.metadata["last_verified"] = time.time()
                profile.metadata["blockchain_status"] = "verified"
            return redirect(url_for("web.dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_did" in session:
        return redirect(url_for("web.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        agent_type = request.form.get("agent_type", "human")
        display_name = request.form.get("display_name", "").strip() or username
        bio = request.form.get("bio", "").strip()[:280]
        state = current_app.app_state
        if not username or not password:
            flash("Username and password are required", "error")
        elif password != confirm:
            flash("Passwords do not match", "error")
        elif username in state.user_registry:
            flash("Username already taken", "error")
        else:
            user = create_user(username, password, agent_type)
            state.user_registry[username] = user
            state.did_to_username[user.did] = username
            # Auto-create a profile for the user
            dtype = DeviceType.AGENT if agent_type == "ai" else DeviceType.HUMAN
            metadata = {}
            if bio:
                metadata["bio"] = bio
            # Optional social links from registration form
            from urllib.parse import urlparse as _urlparse
            social_links = {}
            for platform in ("facebook", "linkedin", "instagram", "youtube", "twitter"):
                url_val = request.form.get(f"sl_{platform}", "").strip()
                if url_val:
                    parsed = _urlparse(url_val)
                    if parsed.scheme in ("http", "https") and parsed.netloc:
                        social_links[platform] = url_val
            if social_links:
                metadata["social_links"] = social_links
            profile = Profile(did=user.did, display_name=display_name, device_type=dtype, metadata=metadata)
            state.network_map.add_profile(profile)
            session["user_did"] = user.did
            session["username"] = user.username
            session["agent_type"] = user.agent_type
            return redirect(url_for("web.dashboard"))
    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
