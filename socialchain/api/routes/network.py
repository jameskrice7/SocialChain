from flask import Blueprint, jsonify, request, current_app

network_bp = Blueprint("network", __name__)


@network_bp.route("/api/network/peers", methods=["GET"])
def list_peers():
    state = current_app.app_state
    return jsonify({"peers": state.network_node.get_peers()}), 200


@network_bp.route("/api/network/peers", methods=["POST"])
def register_peer():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    did = data.get("did")
    address = data.get("address")
    if not did or not address:
        return jsonify({"error": "Missing did or address"}), 400
    state.network_node.register_peer(did, address)
    return jsonify({"message": f"Peer {did} registered at {address}"}), 201
