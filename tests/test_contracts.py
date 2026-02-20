"""Tests for smart contract blockchain integration."""
import pytest
from socialchain.blockchain.contract import SmartContract, ContractStatus
from socialchain.blockchain import Blockchain


def test_contract_creation():
    contract = SmartContract(
        creator_did="did:socialchain:abc123",
        title="Test Agreement",
        description="A test contract",
        participants=["did:socialchain:abc123", "did:socialchain:def456"],
        terms={"deliverable": "report", "deadline": "2026-04-01"},
    )
    assert contract.title == "Test Agreement"
    assert contract.status == ContractStatus.PENDING
    assert len(contract.participants) == 2
    assert contract.contract_id is not None
    assert contract.tx_ids == []


def test_contract_hash_stability():
    contract = SmartContract(
        creator_did="did:socialchain:abc",
        title="Hash Test",
        terms={"key": "val"},
    )
    h1 = contract.compute_hash()
    h2 = contract.compute_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_contract_to_dict():
    contract = SmartContract(
        creator_did="did:socialchain:abc",
        title="Dict Test",
    )
    d = contract.to_dict()
    assert d["title"] == "Dict Test"
    assert d["status"] == "PENDING"
    assert "contract_hash" in d
    assert "created_at" in d


def test_contract_from_dict_roundtrip():
    contract = SmartContract(
        creator_did="did:socialchain:abc",
        title="Roundtrip",
        description="desc",
        participants=["did:socialchain:x"],
        terms={"k": "v"},
    )
    contract.status = ContractStatus.ACTIVE
    d = contract.to_dict()
    restored = SmartContract.from_dict(d)
    assert restored.contract_id == contract.contract_id
    assert restored.title == contract.title
    assert restored.status == ContractStatus.ACTIVE
    assert restored.participants == contract.participants


def test_contract_api_create(client):
    # Must register a user first via register endpoint
    client.post("/register", data={
        "username": "contractuser",
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        user_did = sess.get("user_did")
    assert user_did

    resp = client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "API Test Contract",
        "description": "Created via API",
        "participants": [user_did],
        "terms": {"task": "deliver report"},
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["contract"]["title"] == "API Test Contract"
    assert data["contract"]["status"] == "ACTIVE"
    assert "tx_id" in data
    # return the contract_id for potential use (tests should not return values)
    assert data["contract"]["contract_id"]


def test_contract_api_list(client):
    client.post("/register", data={
        "username": "listuser",
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        user_did = sess.get("user_did")

    client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "List Test",
        "participants": [],
    })
    resp = client.get("/api/contracts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "contracts" in data
    assert data["count"] >= 1


def test_contract_api_complete_and_verify(client):
    client.post("/register", data={
        "username": "cvuser",
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        user_did = sess.get("user_did")

    # Create
    create_resp = client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "Complete+Verify",
        "participants": [],
    })
    cid = create_resp.get_json()["contract"]["contract_id"]

    # Complete
    complete_resp = client.patch(f"/api/contracts/{cid}/complete", json={
        "completer_did": user_did,
        "completion_data": {"outcome": "success"},
    })
    assert complete_resp.status_code == 200
    assert complete_resp.get_json()["contract"]["status"] == "COMPLETED"

    # Verify
    verify_resp = client.patch(f"/api/contracts/{cid}/verify", json={
        "verifier_did": user_did,
    })
    assert verify_resp.status_code == 200
    assert verify_resp.get_json()["contract"]["status"] == "VERIFIED"


def test_contract_api_transactions(client):
    client.post("/register", data={
        "username": "txcontractuser",
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        user_did = sess.get("user_did")

    create_resp = client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "TX Test",
        "participants": [],
    })
    cid = create_resp.get_json()["contract"]["contract_id"]

    resp = client.get(f"/api/contracts/{cid}/transactions")
    assert resp.status_code == 200
    data = resp.get_json()
    # At least the creation tx should be in pending
    assert len(data["transactions"]) >= 1
    assert data["transactions"][0]["data"]["type"] == "contract_create"


def test_contract_api_not_found(client):
    resp = client.get("/api/contracts/nonexistent-id")
    assert resp.status_code == 404


def test_contract_invalid_participant(client):
    """Test that invalid participant DIDs are rejected."""
    client.post("/register", data={
        "username": "invalidpartuser",
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        user_did = sess.get("user_did")

    resp = client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "Invalid Participant",
        "participants": ["not-a-valid-did", user_did],
    })
    assert resp.status_code == 400
    assert "Invalid participant DID" in resp.get_json()["error"]

    # Valid DID format should succeed
    resp2 = client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "Valid Participant",
        "participants": [user_did],
    })
    assert resp2.status_code == 201


def test_contract_complete_wrong_status(client):
    client.post("/register", data={
        "username": "statususer",
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        user_did = sess.get("user_did")

    create_resp = client.post("/api/contracts", json={
        "creator_did": user_did,
        "title": "Status Flow Test",
        "participants": [],
    })
    cid = create_resp.get_json()["contract"]["contract_id"]

    # Complete it
    client.patch(f"/api/contracts/{cid}/complete", json={"completer_did": user_did})
    # Verify it
    client.patch(f"/api/contracts/{cid}/verify", json={"verifier_did": user_did})
    # Try to complete again (should fail)
    resp = client.patch(f"/api/contracts/{cid}/complete", json={"completer_did": user_did})
    assert resp.status_code == 400
