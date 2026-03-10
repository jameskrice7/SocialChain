"""Tests for the new security, blockchain, and API enhancements."""

import json
import pytest
from socialchain.blockchain import (
    Blockchain, Transaction, TransactionType, Identity,
    sha256, double_sha256, hmac_sha256,
    derive_key, verify_key,
    merkle_root, difficulty_target, hash_meets_difficulty,
    sigmoid, log_scale, weighted_average,
)


# ---------------------------------------------------------------------------
# crypto.py – hashing & math helpers
# ---------------------------------------------------------------------------

class TestCryptoHelpers:
    def test_sha256(self):
        h = sha256("hello")
        assert len(h) == 64
        assert h == sha256("hello")  # deterministic

    def test_double_sha256(self):
        h = double_sha256("hello")
        assert len(h) == 64
        assert h != sha256("hello")  # double != single

    def test_hmac_sha256(self):
        h = hmac_sha256(b"key", b"message")
        assert len(h) == 64

    def test_derive_key_and_verify(self):
        dk, salt = derive_key("mypassword")
        assert len(dk) == 64
        assert len(salt) == 32
        assert verify_key("mypassword", dk, salt) is True
        assert verify_key("wrongpassword", dk, salt) is False

    def test_merkle_root_empty(self):
        assert merkle_root([]) == "0" * 64

    def test_merkle_root_single(self):
        h = sha256("tx1")
        assert merkle_root([h]) == h

    def test_merkle_root_multiple(self):
        hashes = [sha256(f"tx{i}") for i in range(4)]
        root = merkle_root(hashes)
        assert len(root) == 64
        assert root != hashes[0]

    def test_merkle_root_odd_count(self):
        hashes = [sha256(f"tx{i}") for i in range(3)]
        root = merkle_root(hashes)
        assert len(root) == 64

    def test_difficulty_target(self):
        assert difficulty_target(4).startswith("0000")
        assert len(difficulty_target(4)) == 64

    def test_hash_meets_difficulty(self):
        assert hash_meets_difficulty("0000abcdef", 4) is True
        assert hash_meets_difficulty("000abcdef", 4) is False
        assert hash_meets_difficulty("abcdef", 4) is False

    def test_sigmoid(self):
        assert sigmoid(0) == 0.5
        assert sigmoid(100) > 0.99
        assert sigmoid(-100) < 0.01

    def test_log_scale(self):
        assert log_scale(0) == 0.0
        assert log_scale(9) > 0
        assert log_scale(-9) < 0

    def test_weighted_average(self):
        assert weighted_average([10, 20], [1, 1]) == 15.0
        assert weighted_average([10, 20], [0, 0]) == 0.0
        assert weighted_average([10, 20], [2, 1]) == pytest.approx(40 / 3)


# ---------------------------------------------------------------------------
# Transaction enhancements
# ---------------------------------------------------------------------------

class TestTransactionType:
    def test_tx_type_auto_infer_mining_reward(self):
        tx = Transaction(sender="NETWORK", recipient="alice", data={"reward": 1})
        assert tx.tx_type == TransactionType.MINING_REWARD

    def test_tx_type_auto_infer_from_data(self):
        tx = Transaction(sender="alice", recipient="bob", data={"type": "agent_registration"})
        assert tx.tx_type == TransactionType.AGENT_REGISTRATION

    def test_tx_type_explicit(self):
        tx = Transaction(
            sender="alice", recipient="bob",
            data={"foo": 1}, tx_type=TransactionType.CONTRACT_DEPLOY,
        )
        assert tx.tx_type == TransactionType.CONTRACT_DEPLOY

    def test_tx_type_default_transfer(self):
        tx = Transaction(sender="alice", recipient="bob", data={"amount": 5})
        assert tx.tx_type == TransactionType.TRANSFER

    def test_timestamp_auto(self):
        tx = Transaction(sender="alice", recipient="bob", data={})
        assert tx.timestamp is not None
        assert isinstance(tx.timestamp, float)

    def test_to_dict_includes_new_fields(self):
        tx = Transaction(sender="a", recipient="b", data={}, tx_type="custom", timestamp=12345.0)
        d = tx.to_dict()
        assert d["tx_type"] == "custom"
        assert d["timestamp"] == 12345.0

    def test_from_dict_preserves_new_fields(self):
        tx = Transaction(sender="a", recipient="b", data={}, tx_type="governance", timestamp=99.0)
        tx2 = Transaction.from_dict(tx.to_dict())
        assert tx2.tx_type == "governance"
        assert tx2.timestamp == 99.0


# ---------------------------------------------------------------------------
# Blockchain – signature verification
# ---------------------------------------------------------------------------

class TestSignatureVerification:
    def test_verify_network_tx(self):
        bc = Blockchain()
        tx = Transaction(sender="NETWORK", recipient="alice", data={"reward": 1})
        assert bc.verify_transaction(tx) is True

    def test_verify_unsigned_tx(self):
        bc = Blockchain()
        tx = Transaction(sender="did:socialchain:abcdef", recipient="bob", data={})
        assert bc.verify_transaction(tx) is False

    def test_verify_signed_tx(self):
        bc = Blockchain()
        identity = Identity()
        tx = Transaction(sender=identity.did, recipient="bob", data={"amount": 10})
        payload = json.dumps(tx.to_dict(), sort_keys=True).encode()
        tx.signature = identity.sign(payload)
        assert bc.verify_transaction(tx) is True

    def test_verify_tampered_tx(self):
        bc = Blockchain()
        identity = Identity()
        tx = Transaction(sender=identity.did, recipient="bob", data={"amount": 10})
        payload = json.dumps(tx.to_dict(), sort_keys=True).encode()
        tx.signature = identity.sign(payload)
        tx.data = {"amount": 999}  # tamper
        assert bc.verify_transaction(tx) is False

    def test_verify_invalid_sender(self):
        bc = Blockchain()
        tx = Transaction(sender="not-a-did", recipient="bob", data={}, signature="deadbeef")
        assert bc.verify_transaction(tx) is False


# ---------------------------------------------------------------------------
# Blockchain – balance & queries
# ---------------------------------------------------------------------------

class TestBlockchainQueries:
    def test_get_balance_zero(self):
        bc = Blockchain()
        assert bc.get_balance("did:socialchain:nobody") == 0

    def test_get_balance_after_mining(self):
        bc = Blockchain()
        miner = "did:socialchain:miner123"
        tx = Transaction(sender="alice", recipient="bob", data={"msg": "hi"})
        bc.add_transaction(tx)
        bc.mine_block(miner)
        assert bc.get_balance(miner) == 1

    def test_get_transactions_for(self):
        bc = Blockchain()
        tx = Transaction(sender="alice", recipient="bob", data={"msg": "hi"})
        bc.add_transaction(tx)
        bc.mine_block("alice")
        results = bc.get_transactions_for("alice")
        assert len(results) >= 1
        senders = [r["sender"] for r in results]
        recipients = [r["recipient"] for r in results]
        assert "alice" in senders or "alice" in recipients

    def test_get_merkle_root(self):
        bc = Blockchain()
        tx = Transaction(sender="alice", recipient="bob", data={"msg": "hi"})
        bc.add_transaction(tx)
        bc.mine_block("miner")
        root = bc.get_merkle_root(1)
        assert len(root) == 64
        assert root != "0" * 64

    def test_get_merkle_root_invalid_index(self):
        bc = Blockchain()
        assert bc.get_merkle_root(999) == "0" * 64


# ---------------------------------------------------------------------------
# API endpoints – balance, tx history, verify-tx, agent actions
# ---------------------------------------------------------------------------

class TestNewAPIEndpoints:
    @pytest.fixture
    def app_state(self):
        from socialchain.api.app import AppState
        return AppState()

    @pytest.fixture
    def app(self, app_state):
        from socialchain.api.app import create_app
        application = create_app(state=app_state)
        application.config["TESTING"] = True
        return application

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_get_balance_endpoint(self, client):
        resp = client.get("/api/balance/did:socialchain:test123")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "balance" in data
        assert data["did"] == "did:socialchain:test123"

    def test_get_transactions_endpoint(self, client):
        resp = client.get("/api/transactions/did:socialchain:test123")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "transactions" in data
        assert "count" in data

    def test_verify_tx_endpoint(self, client):
        identity = Identity()
        tx = Transaction(sender=identity.did, recipient="bob", data={"msg": "test"})
        payload = json.dumps(tx.to_dict(), sort_keys=True).encode()
        tx.signature = identity.sign(payload)
        resp = client.post("/api/verify-tx", json=tx.to_dict())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True

    def test_verify_tx_endpoint_invalid(self, client):
        resp = client.post("/api/verify-tx", json={
            "sender": "did:socialchain:fake",
            "recipient": "bob",
            "data": {},
            "signature": "deadbeef",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False

    def test_agent_internet_action(self, client, app_state):
        from socialchain.agents.agent import AIAgent
        agent = AIAgent(name="TestBot", capabilities=["chat"])
        agent.register_on_blockchain(app_state.blockchain)
        app_state.agent_registry[agent.did] = agent

        resp = client.post(f"/api/agents/{agent.did}/actions", json={
            "action_type": "web_search",
            "target_url": "https://example.com",
            "description": "Search for blockchain info",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["action_type"] == "web_search"
        assert "tx_id" in data

    def test_agent_internet_action_missing_description(self, client, app_state):
        from socialchain.agents.agent import AIAgent
        agent = AIAgent(name="TestBot2", capabilities=[])
        agent.register_on_blockchain(app_state.blockchain)
        app_state.agent_registry[agent.did] = agent

        resp = client.post(f"/api/agents/{agent.did}/actions", json={
            "action_type": "web_search",
        })
        assert resp.status_code == 400

    def test_agent_internet_action_not_found(self, client):
        resp = client.post("/api/agents/did:socialchain:nonexistent/actions", json={
            "description": "test",
        })
        assert resp.status_code == 404

    def test_create_transaction_with_type(self, client):
        resp = client.post("/api/transactions", json={
            "sender": "alice",
            "recipient": "bob",
            "data": {"msg": "hello"},
            "tx_type": "transfer",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "tx_id" in data
