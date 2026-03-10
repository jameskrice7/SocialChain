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
        tx_type=data.get("tx_type"),
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


@chain_bp.route("/api/balance/<path:did>", methods=["GET"])
def get_balance(did):
    """Return the mining-reward balance for *did*."""
    state = current_app.app_state
    balance = state.blockchain.get_balance(did)
    return jsonify({"did": did, "balance": balance}), 200


@chain_bp.route("/api/transactions/<path:did>", methods=["GET"])
def get_transactions_for(did):
    """Return all mined transactions involving *did*."""
    state = current_app.app_state
    txs = state.blockchain.get_transactions_for(did)
    return jsonify({"did": did, "transactions": txs, "count": len(txs)}), 200


@chain_bp.route("/api/verify-tx", methods=["POST"])
def verify_transaction():
    """Verify a transaction's ECDSA signature."""
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    required = ["sender", "recipient", "data"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    tx = Transaction.from_dict(data)
    valid = state.blockchain.verify_transaction(tx)
    return jsonify({"valid": valid, "tx_id": tx.tx_id}), 200
