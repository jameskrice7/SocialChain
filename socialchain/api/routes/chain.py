from flask import Blueprint, jsonify, request, current_app
from ...blockchain.transaction import Transaction

chain_bp = Blueprint("chain", __name__)


@chain_bp.route("/api/chain", methods=["GET"])
def get_chain():
    state = current_app.app_state
    return jsonify(state.blockchain.to_dict()), 200


@chain_bp.route("/api/transactions", methods=["POST"])
def create_transaction():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    required = ["sender", "recipient", "data"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    tx = Transaction(
        sender=data["sender"],
        recipient=data["recipient"],
        data=data["data"],
        signature=data.get("signature"),
    )
    block_index = state.blockchain.add_transaction(tx)
    return jsonify({"message": f"Transaction added to block {block_index}", "tx_id": tx.tx_id}), 201


@chain_bp.route("/api/mine", methods=["POST"])
def mine():
    state = current_app.app_state
    data = request.get_json() or {}
    miner_did = data.get("miner_did", state.network_node.node_id)
    if not state.blockchain.pending_transactions:
        return jsonify({"message": "No pending transactions to mine"}), 400
    block = state.blockchain.mine_block(miner_did)
    return jsonify({"message": "Block mined", "block": block.to_dict()}), 200
