import time

from flask import Blueprint, jsonify, request, current_app

from ...blockchain.contract import SmartContract, ContractStatus
from ...blockchain.transaction import Transaction

contracts_bp = Blueprint("contracts", __name__)


@contracts_bp.route("/api/contracts", methods=["GET"])
def list_contracts():
    state = current_app.app_state
    contracts = [c.to_dict() for c in state.contracts.values()]
    return jsonify({"contracts": contracts, "count": len(contracts)}), 200


@contracts_bp.route("/api/contracts", methods=["POST"])
def create_contract():
    """Create a new smart contract and anchor it to the blockchain."""
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    required = ["creator_did", "title"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400

    # Validate participants list
    participants = data.get("participants", [])
    if not isinstance(participants, list):
        return jsonify({"error": "participants must be a list"}), 400

    contract = SmartContract(
        creator_did=data["creator_did"],
        title=data["title"],
        description=data.get("description", ""),
        participants=participants,
        terms=data.get("terms", {}),
    )

    # Record contract creation on the blockchain
    tx = Transaction(
        sender=data["creator_did"],
        recipient="NETWORK",
        data={
            "type": "contract_create",
            "contract_id": contract.contract_id,
            "title": contract.title,
            "participants": contract.participants,
            "contract_hash": contract.compute_hash(),
            "timestamp": contract.created_at,
        },
    )
    state.blockchain.add_transaction(tx)
    contract.tx_ids.append(tx.tx_id)
    contract.status = ContractStatus.ACTIVE

    state.contracts[contract.contract_id] = contract
    return jsonify({"message": "Contract created", "contract": contract.to_dict(), "tx_id": tx.tx_id}), 201


@contracts_bp.route("/api/contracts/<contract_id>", methods=["GET"])
def get_contract(contract_id):
    state = current_app.app_state
    contract = state.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    return jsonify({"contract": contract.to_dict()}), 200


@contracts_bp.route("/api/contracts/<contract_id>/complete", methods=["PATCH"])
def complete_contract(contract_id):
    """Mark a contract as completed and record it on the blockchain."""
    state = current_app.app_state
    contract = state.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    if contract.status not in (ContractStatus.ACTIVE, ContractStatus.PENDING):
        return jsonify({"error": f"Cannot complete contract with status {contract.status.value}"}), 400

    data = request.get_json() or {}
    contract.completion_data = data.get("completion_data", {})
    contract.status = ContractStatus.COMPLETED
    contract.updated_at = time.time()

    tx = Transaction(
        sender=data.get("completer_did", contract.creator_did),
        recipient="NETWORK",
        data={
            "type": "contract_complete",
            "contract_id": contract.contract_id,
            "completion_data": contract.completion_data,
            "timestamp": contract.updated_at,
        },
    )
    state.blockchain.add_transaction(tx)
    contract.tx_ids.append(tx.tx_id)

    return jsonify({"message": "Contract completed", "contract": contract.to_dict(), "tx_id": tx.tx_id}), 200


@contracts_bp.route("/api/contracts/<contract_id>/verify", methods=["PATCH"])
def verify_contract(contract_id):
    """Verify a completed contract and anchor verification to the blockchain."""
    state = current_app.app_state
    contract = state.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    if contract.status != ContractStatus.COMPLETED:
        return jsonify({"error": "Only completed contracts can be verified"}), 400

    data = request.get_json() or {}
    contract.status = ContractStatus.VERIFIED
    contract.updated_at = time.time()

    tx = Transaction(
        sender=data.get("verifier_did", contract.creator_did),
        recipient="NETWORK",
        data={
            "type": "contract_verify",
            "contract_id": contract.contract_id,
            "contract_hash": contract.compute_hash(),
            "timestamp": contract.updated_at,
        },
    )
    state.blockchain.add_transaction(tx)
    contract.tx_ids.append(tx.tx_id)

    return jsonify({"message": "Contract verified", "contract": contract.to_dict(), "tx_id": tx.tx_id}), 200


@contracts_bp.route("/api/contracts/<contract_id>/transactions", methods=["GET"])
def get_contract_transactions(contract_id):
    """Return all blockchain transactions associated with a contract."""
    state = current_app.app_state
    contract = state.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404

    matching_txs = []
    for block in state.blockchain.chain:
        for tx in block.transactions:
            tx_dict = tx.to_dict()
            if (
                isinstance(tx_dict.get("data"), dict)
                and tx_dict["data"].get("contract_id") == contract_id
            ):
                matching_txs.append({**tx_dict, "block_index": block.index})
    # Also check pending transactions
    for tx in state.blockchain.pending_transactions:
        tx_dict = tx.to_dict()
        if (
            isinstance(tx_dict.get("data"), dict)
            and tx_dict["data"].get("contract_id") == contract_id
        ):
            matching_txs.append({**tx_dict, "block_index": "pending"})

    return jsonify({"contract_id": contract_id, "transactions": matching_txs}), 200
