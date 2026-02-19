from flask import Blueprint, jsonify, request, current_app
from ...social.profile import Profile, DeviceType
from ...social.request import SocialRequest, RequestAction, RequestStatus

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
