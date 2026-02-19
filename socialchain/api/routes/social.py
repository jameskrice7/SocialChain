import time

from flask import Blueprint, jsonify, request, current_app
from ...social.profile import Profile, DeviceType
from ...social.request import SocialRequest, RequestAction, RequestStatus
from ...blockchain.transaction import Transaction

social_bp = Blueprint("social", __name__)


@social_bp.route("/api/social/profiles", methods=["GET"])
def list_profiles():
    state = current_app.app_state
    profiles = [p.to_dict() for p in state.network_map.list_profiles()]
    return jsonify({"profiles": profiles}), 200


@social_bp.route("/api/social/profiles", methods=["POST"])
def create_profile():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if "did" not in data or "display_name" not in data:
        return jsonify({"error": "Missing did or display_name"}), 400
    profile = Profile.from_dict(data)
    state.network_map.add_profile(profile)
    return jsonify({"message": "Profile created", "profile": profile.to_dict()}), 201


@social_bp.route("/api/social/map", methods=["GET"])
def get_network_map():
    state = current_app.app_state
    return jsonify({"map": state.network_map.visualize()}), 200


@social_bp.route("/api/social/requests", methods=["POST"])
def create_request():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    required = ["requester_did", "target_did", "action"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    try:
        social_req = SocialRequest.from_dict(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    state.social_requests[social_req.request_id] = social_req
    return jsonify({"message": "Request created", "request": social_req.to_dict()}), 201


@social_bp.route("/api/social/requests", methods=["GET"])
def list_requests():
    state = current_app.app_state
    requests_list = [r.to_dict() for r in state.social_requests.values()]
    return jsonify({"requests": requests_list}), 200


@social_bp.route("/api/social/requests/<request_id>", methods=["PATCH"])
def update_request(request_id):
    state = current_app.app_state
    if request_id not in state.social_requests:
        return jsonify({"error": "Request not found"}), 404
    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"error": "Missing status"}), 400
    try:
        new_status = RequestStatus(data["status"])
    except ValueError:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 400
    state.social_requests[request_id].status = new_status
    return jsonify({"message": "Status updated", "request": state.social_requests[request_id].to_dict()}), 200


@social_bp.route("/api/social/profiles/<path:did>", methods=["GET"])
def get_profile(did):
    state = current_app.app_state
    profile = state.network_map.get_profile(did)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    connections = state.network_map.get_connections(did)
    data = profile.to_dict()
    data["connections"] = connections
    return jsonify({"profile": data}), 200


@social_bp.route("/api/social/connections", methods=["POST"])
def add_connection():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    did_a = data.get("did_a")
    did_b = data.get("did_b")
    if not did_a or not did_b:
        return jsonify({"error": "Missing did_a or did_b"}), 400
    ok = state.network_map.add_connection(did_a, did_b)
    if not ok:
        return jsonify({"error": "One or both profiles not found"}), 404
    return jsonify({"message": f"Connection added between {did_a} and {did_b}"}), 201


@social_bp.route("/api/social/profiles/<path:did>/verify", methods=["POST"])
def verify_profile(did):
    """Record a blockchain status-verification transaction for a profile."""
    state = current_app.app_state
    profile = state.network_map.get_profile(did)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    tx = Transaction(
        sender=did,
        recipient="NETWORK",
        data={"type": "status_update", "status": "active", "timestamp": time.time()},
    )
    state.blockchain.add_transaction(tx)
    profile.metadata["last_verified"] = time.time()
    profile.metadata["blockchain_status"] = "verified"
    return jsonify({"message": "Status verified on chain", "tx_id": tx.tx_id, "last_verified": profile.metadata["last_verified"]}), 200


@social_bp.route("/api/social/profiles/<path:did>/social-links", methods=["PATCH"])
def update_social_links(did):
    """Update social media links for a profile."""
    state = current_app.app_state
    profile = state.network_map.get_profile(did)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    from urllib.parse import urlparse
    allowed = {"facebook", "linkedin", "instagram", "youtube"}
    links = {}
    for k, v in data.items():
        if k not in allowed:
            continue
        if not isinstance(v, str):
            return jsonify({"error": f"Invalid value for {k}"}), 400
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return jsonify({"error": f"Invalid URL for {k}: must be http/https"}), 400
        links[k] = v
    profile.metadata.setdefault("social_links", {}).update(links)
    return jsonify({"message": "Social links updated", "social_links": profile.metadata["social_links"]}), 200


@social_bp.route("/api/social/external-contacts", methods=["POST"])
def add_external_contact():
    """Add an external (non-SocialChain) contact discovered from social platforms."""
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    required = ["owner_did", "name", "platform"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    owner_did = data["owner_did"]
    profile = state.network_map.get_profile(owner_did)
    if not profile:
        return jsonify({"error": "Owner profile not found"}), 404
    allowed_platforms = {"facebook", "linkedin", "instagram", "youtube"}
    name = str(data["name"])[:128].strip()
    platform = str(data["platform"]).lower()
    if platform not in allowed_platforms:
        return jsonify({"error": f"Platform must be one of {sorted(allowed_platforms)}"}), 400
    platform_id = str(data.get("platform_id", ""))[:256].strip()
    contacts = profile.metadata.setdefault("external_contacts", [])
    contact = {
        "name": name,
        "platform": platform,
        "platform_id": platform_id,
        "invited": bool(data.get("invited", False)),
    }
    contacts.append(contact)
    return jsonify({"message": "External contact added", "contact": contact}), 201
