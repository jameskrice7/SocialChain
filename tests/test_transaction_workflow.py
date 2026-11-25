from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from socialchain.blockchain import Block, Blockchain, Identity, Transaction
from socialchain.network import NetworkNode


@pytest.fixture(autouse=True)
def fast_mining(monkeypatch):
    monkeypatch.setattr(Blockchain, "DIFFICULTY", 1)


def test_dashboard_signed_transaction_lifecycle(client):
    payload = {"recipient": "bob", "data": {"message": "hello"}}
    assert client.post("/api/transactions", json=payload).status_code == 401
    client.post("/register", data={"username": "alice", "password": "test", "confirm_password": "test"})
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201
    tx_id = response.json["tx_id"]
    url = "/api/transactions?q=" + tx_id
    pending, = client.get(url + "&status=pending").json["transactions"]
    assert pending["signature_status"] == "valid"
    assert pending["block_index"] is None
    assert client.get("/api/mempool/signatures").json == {
        "valid": 1, "invalid": 0, "unsigned": 0, "system": 0,
    }

    block = client.post("/api/mine", json={"miner_did": "alice"}).json["block"]
    confirmed, = client.get(url + "&status=confirmed").json["transactions"]
    assert confirmed["signature"] == pending["signature"]
    assert confirmed["block_hash"] == block["hash"]
    assert confirmed["block_index"] == 1
    assert confirmed["signature_status"] == "valid"
    assert client.get(url + "&status=pending").json["transactions"] == []
    assert client.get("/api/balance/alice").json["balance"] == 1


def test_external_signature_is_preserved_and_duplicate_rejected(client):
    signer = Identity()
    tx = Transaction(signer.did, "recipient", {"hello": "world"})
    tx.signature = signer.sign(tx.signing_payload())
    payload = tx.to_dict()
    assert client.post("/api/transactions", json=payload).json["tx_id"] == tx.tx_id
    assert client.post("/api/transactions", json=payload).status_code == 409
    assert client.post("/api/transactions", json={**payload, "data": {}}).status_code == 400
    assert client.post("/api/mine", json={}).status_code == 200
    assert client.post("/api/transactions", json=payload).status_code == 409


def test_page_order_filter_and_signature_report(client, app_state):
    ledger = app_state.blockchain
    old = Transaction("alice", "bob", None, tx_type="custom")
    ledger.add_transaction(old)
    ledger.mine_block("miner")
    unsigned = Transaction("alice", "carol", 0)
    invalid = Transaction("alice", "dave", False, signature="invalid")
    ledger.add_transaction(unsigned)
    ledger.add_transaction(invalid)
    before = ledger.to_dict()
    assert client.get("/api/mempool/signatures").json == {
        "valid": 0, "invalid": 1, "unsigned": 1, "system": 0,
    }
    first = client.get("/api/transactions?limit=2").json
    assert [tx["tx_id"] for tx in first["transactions"]] == [invalid.tx_id, unsigned.tx_id]
    assert first["has_more"]
    last = client.get("/api/transactions?offset=2&limit=2").json
    assert [tx["signature_status"] for tx in last["transactions"]] == ["system", "unsigned"]
    assert not last["has_more"]
    for query in ["CUSTOM", "bOb", "aLice", old.tx_id.upper()]:
        result = client.get("/api/transactions", query_string={"status": "confirmed", "q": query})
        assert [tx["tx_id"] for tx in result.json["transactions"]] == [old.tx_id]
    assert before == ledger.to_dict()


@pytest.mark.parametrize("query", ["status=unknown", "limit=101", "offset=-1", "limit=nope"])
def test_invalid_page_parameters(client, query):
    assert client.get("/api/transactions?" + query).status_code == 400


def test_summary_is_bounded_and_excludes_payloads(client, app_state):
    ledger = app_state.blockchain
    for i in range(14):
        ledger.add_transaction(Transaction("alice", "bob", {"message": "large payload"}))
        ledger.mine_block("miner")
    ledger.add_transaction(Transaction("bob", "carol", {}))
    summary = client.get("/api/chain/summary").json
    assert (summary["length"], summary["mined_count"], summary["pending_count"]) == (15, 28, 1)
    assert [block["index"] for block in summary["recent_blocks"]] == list(range(14, 2, -1))
    assert all(block["transaction_count"] == 2 and "transactions" not in block
               for block in summary["recent_blocks"])


def test_only_system_rewards_change_mining_balance(client):
    submitted = {"sender": "alice", "recipient": "bob", "data": {"reward": "bonus"}}
    assert client.post("/api/transactions", json=submitted).status_code == 201
    assert client.post("/api/transactions", json={**submitted, "sender": "NETWORK"}).status_code == 400
    client.post("/api/mine", json={"miner_did": "bob"})
    assert client.get("/api/balance/bob").json["balance"] == 1


def test_submissions_during_proof_survive_and_competing_miners_serialize(monkeypatch):
    ledger = Blockchain()
    first = Transaction("alice", "bob", {})
    second = Transaction("bob", "carol", {})
    ledger.add_transaction(first)
    started, resume = Event(), Event()
    proof = ledger._proof_of_work

    def pause_proof(block):
        started.set()
        assert resume.wait(5)
        return proof(block)

    monkeypatch.setattr(ledger, "_proof_of_work", pause_proof)
    with ThreadPoolExecutor(max_workers=3) as pool:
        mining = pool.submit(ledger.mine_block, "miner", require_pending=True)
        assert started.wait(5)
        queued = pool.submit(ledger.add_transaction, second)
        queued.result(timeout=3)
        assert ledger.summary()["pending_count"] == 2
        competing = pool.submit(ledger.mine_block, "other", require_pending=True)
        resume.set()
        assert mining.result().transactions[:-1] == [first]
        assert competing.result().transactions[:-1] == [second]
    assert ledger.mine_block("nobody", require_pending=True) is None
    assert ledger.validate_chain()
    assert ledger.pending_transactions == []


def test_failed_proof_preserves_queue(monkeypatch):
    ledger = Blockchain()
    tx = Transaction("alice", "bob", {})
    ledger.add_transaction(tx)
    monkeypatch.setattr(ledger, "_proof_of_work", Mock(side_effect=RuntimeError("interrupted")))
    with pytest.raises(RuntimeError, match="interrupted"):
        ledger.mine_block("miner")
    assert ledger.pending_transactions == [tx]
    assert len(ledger.chain) == 1


def test_sync_skips_invalid_peer_and_requeues_displaced_work(monkeypatch):
    local, remote = Blockchain(), Blockchain()
    displaced = Transaction("alice", "bob", {})
    confirmed = Transaction("carol", "bob", {})
    pending = Transaction("bob", "alice", {})
    local.add_transaction(displaced)
    local.mine_block("former-miner")
    local.add_transaction(confirmed)
    local.add_transaction(pending)
    remote.add_transaction(confirmed)
    remote.mine_block("peer-miner")
    remote.mine_block("peer-miner")
    broken = remote.to_dict()
    broken["chain"][0]["hash"] = "incorrect"
    responses = [Mock(json=lambda: broken), Mock(json=remote.to_dict)]
    monkeypatch.setattr("socialchain.network.node.requests.get", Mock(side_effect=responses))
    node = NetworkNode()
    node.register_peer("first", "first.test")
    node.register_peer("second", "second.test")
    assert node.sync_chain(local)
    assert local.last_block.hash == remote.last_block.hash
    assert local.pending_transactions == [displaced, pending]
    assert local.get_balance("former-miner") == 0
    assert local.get_balance("peer-miner") == 2


def test_tip_change_during_proof_retries_against_adopted_chain(monkeypatch):
    ledger, peer = Blockchain(), Blockchain()
    local = Transaction("alice", "bob", {})
    ledger.add_transaction(local)
    peer.mine_block("peer")
    proof = ledger._proof_of_work

    def change_tip(block):
        assert ledger.adopt_chain(peer.chain)
        monkeypatch.setattr(ledger, "_proof_of_work", proof)
        return proof(block)

    monkeypatch.setattr(ledger, "_proof_of_work", change_tip)
    new_block = ledger.mine_block("miner", require_pending=True)
    assert len(peer.chain) == 2
    assert new_block.index == 2
    assert new_block.previous_hash == peer.chain[1].hash
    assert new_block.transactions[:-1] == [local]
    assert ledger.validate_chain()


def test_replayed_peer_block_is_rejected_even_with_valid_proof():
    ledger, peer = Blockchain(), Blockchain()
    tx = Transaction("alice", "bob", {})
    peer.add_transaction(tx)
    peer.mine_block("peer")
    assert ledger.adopt_chain(list(peer.chain))
    duplicate = Block(2, [tx], peer.last_block.hash)
    duplicate.nonce, duplicate.hash = peer._proof_of_work(duplicate)
    assert not ledger.add_block(duplicate)
    assert not ledger.adopt_chain(peer.chain + [duplicate])
    assert ledger.validate_chain()
