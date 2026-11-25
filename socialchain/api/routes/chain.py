from flask import Blueprint, jsonify, request, current_app, session
from ...blockchain.blockchain import DuplicateTransaction
from ...blockchain.transaction import Transaction, TransactionType

chain_bp = Blueprint("chain", __name__)


@chain_bp.route("/api/chain", methods=["GET"])
def get_chain():
    state = current_app.app_state
    return jsonify(state.blockchain.to_dict()), 200


@chain_bp.get("/api/chain/summary")
def chain_summary():
    return jsonify(current_app.app_state.blockchain.summary())


@chain_bp.get("/api/transactions")
def list_transactions():
    status = request.args.get("status", "all")
    if status not in {"all", "pending", "confirmed"}:
        return jsonify(error="status must be all, pending or confirmed"), 400
    try:
        limit = int(request.args.get("limit", 25))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify(error="limit and offset must be integers"), 400
    if not 1 <= limit <= 100 or not 0 <= offset <= 2**31 - 1:
        return jsonify(error="limit must be 1–100 and offset must be 0–2147483647"), 400
    query = request.args.get("q", "").strip().casefold()
    return jsonify(current_app.app_state.blockchain.transaction_page(status, query, offset, limit))


@chain_bp.get("/api/mempool/signatures")
def pending_signatures():
    return jsonify(current_app.app_state.blockchain.pending_signatures())


@chain_bp.post("/api/transactions")
def create_transaction():
    state = current_app.app_state
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "data" not in data:
        return jsonify(error="Provide a JSON object with recipient and data"), 400
    # Omitting sender asks the server to sign with the current session's identity.
    signer = None
    if "sender" not in data:
        signer = state.user_registry.get(session.get("username"))
        if signer is None or signer.did != session.get("user_did"):
            return jsonify(error="Sign in to submit using your identity"), 401
        data["sender"] = signer.did
    if not all(isinstance(data.get(k), str) and data[k].strip() for k in ("sender", "recipient")):
        return jsonify(error="sender and recipient must be non-empty strings"), 400
    if data.get("tx_type") is not None and not isinstance(data["tx_type"], str):
        return jsonify(error="tx_type must be a string"), 400

    if data.get("signature") is not None:
        if signer or not isinstance(data.get("tx_id"), str) or not data["tx_id"]:
            return jsonify(error="Signed submissions require the original sender and tx_id"), 400
        tx = Transaction.from_dict(data)
        if tx.sender == "NETWORK" or not state.blockchain.verify_transaction(tx):
            return jsonify(error="Invalid transaction signature"), 400
    else:
        tx = Transaction(sender=data["sender"], recipient=data["recipient"],
                         data=data["data"], tx_type=data.get("tx_type"))
        if signer:
            tx.signature = signer.identity.sign(tx.signing_payload())
    if tx.sender == "NETWORK" or tx.tx_type == TransactionType.MINING_REWARD:
        return jsonify(error="Mining rewards are created by the miner"), 400
    try:
        state.blockchain.add_transaction(tx)
    except DuplicateTransaction:
        return jsonify(error="Transaction already submitted", tx_id=tx.tx_id), 409
    return jsonify(message="Transaction queued for mining", tx_id=tx.tx_id), 201


@chain_bp.route("/api/mine", methods=["POST"])
def mine():
    state = current_app.app_state
    data = request.get_json() or {}
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    miner_did = data.get("miner_did", state.network_node.node_id)
    if not isinstance(miner_did, str) or not miner_did.strip():
        return jsonify(error="miner_did must be a non-empty string"), 400
    block = state.blockchain.mine_block(miner_did, require_pending=True)
    if block is None:
        return jsonify({"message": "No pending transactions to mine"}), 400
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
