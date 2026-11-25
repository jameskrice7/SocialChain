import hashlib
import json
import time
from threading import Event

import pytest

from socialchain.blockchain import Blockchain, Block, Transaction


@pytest.fixture(autouse=True)
def low_difficulty(monkeypatch):
    monkeypatch.setattr(Blockchain, "DIFFICULTY", 1)


def login(client, name):
    response = client.post("/register", data={"username": name, "password": "test", "confirm_password": "test"})
    assert response.status_code == 302


def submit(client, count):
    return [client.post("/api/transactions", json={"sender": "A", "recipient": "B", "data": n}).json["tx_id"]
            for n in range(count)]


def finished(client):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = client.get("/api/mining").json["job"]
        if job and not job["active"]:
            return job
        time.sleep(0.005)
    pytest.fail("Worker did not finish")


def test_nonce_hash_matches_existing_wire_format():
    data = {"nonce": 0, "text": '☃ "nonce": 0,', "nested": [None, False, 1.3]}
    block = Block(14, [Transaction("a", "b", data)], "1" * 64, timestamp=42.25)
    hash_nonce = block.nonce_hasher()
    for nonce in [0, 1, 255, 256, 10000000]:
        fields = block.to_dict()
        del fields["hash"]
        fields["nonce"] = nonce
        expected = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
        assert hash_nonce(nonce) == expected


def test_nonce_search_serializes_transactions_once(monkeypatch):
    tx = Transaction("a", "b", {})
    block = Block(1, [tx], "0" * 64)
    calls = []
    original = tx.to_dict

    def count():
        calls.append(1)
        return original()

    monkeypatch.setattr(tx, "to_dict", count)
    ledger = Blockchain()
    attempts = []
    nonce, digest = ledger._proof_of_work(block, attempts.append)
    assert len(calls) == 1
    assert sum(attempts) == nonce + 1
    block.nonce = nonce
    assert digest == block.compute_hash()


def test_async_batch_and_block_drilldown(client, app_state):
    assert client.get("/api/mining").json["job"] is None
    assert client.post("/api/mining", json={}).status_code == 401
    login(client, "miner")
    assert client.post("/api/mining", json={}).status_code == 409
    txs = submit(client, 4)
    response = client.post("/api/mining", json={"limit": 2, "miner_did": "other"})
    assert response.status_code == 202
    job = finished(client)
    assert job["state"] == "completed" and job["id"] == response.json["job"]["id"]
    block = client.get("/api/blocks/1").json["block"]
    assert job["block_hash"] == block["hash"]
    assert job["attempts"] == block["nonce"] + 1
    assert job["transaction_count"] == 2
    assert [tx["tx_id"] for tx in block["transactions"][:-1]] == txs[:2]
    assert block["transactions"][-1]["recipient"] == app_state.user_registry["miner"].did
    assert [tx.tx_id for tx in app_state.blockchain.pending_transactions] == txs[2:]
    assert client.get("/api/blocks/99").status_code == 404
    assert client.get("/api/blocks/0").json["block"]["transactions"] == []
    assert client.post("/api/mine", json={}).status_code == 200
    assert app_state.blockchain.validate_chain()


@pytest.mark.parametrize("limit", [-1, True, 0, 1.5, "10"])
def test_invalid_batch_size(client, limit):
    login(client, "miner")
    assert client.post("/api/mining", json={"limit": limit}).status_code == 400


def test_cancel_from_owner_keeps_queue_and_allows_restart(client, app, app_state, monkeypatch):
    ledger = app_state.blockchain
    login(client, "miner")
    other = app.test_client()
    login(other, "observer")
    submit(client, 2)
    started, release = Event(), Event()
    proof = ledger._proof_of_work

    def paused(block, report=None):
        report(256)
        started.set()
        assert release.wait(3)
        return proof(block, report)

    monkeypatch.setattr(ledger, "_proof_of_work", paused)
    job = client.post("/api/mining", json={}).json["job"]
    url = "/api/mining/" + job["id"]
    try:
        assert started.wait(2)
        assert other.get("/api/mining").json["job"]["attempts"] == 256
        assert other.post("/api/mining", json={}).status_code == 409
        assert other.delete(url).status_code == 403
        assert app.test_client().delete(url).status_code == 401
        assert client.delete(url).json["job"]["state"] == "cancelling"
        submit(client, 1)
    finally:
        release.set()
    assert finished(client)["state"] == "cancelled"
    assert ledger.summary()["pending_count"] == 3
    assert ledger.summary()["length"] == 1
    monkeypatch.setattr(ledger, "_proof_of_work", proof)
    assert client.post("/api/mining", json={}).status_code == 202
    assert finished(client)["transaction_count"] == 3
    assert client.delete(url).status_code == 404


def test_worker_failure_leaves_job_retryable(client, app_state, monkeypatch):
    login(client, "miner")
    submit(client, 1)

    def fail(block, report=None):
        raise RuntimeError("interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(app_state.blockchain, "_proof_of_work", fail)
        assert client.post("/api/mining", json={}).status_code == 202
        assert finished(client)["state"] == "failed"
    assert app_state.blockchain.summary()["pending_count"] == 1
    assert client.post("/api/mining", json={}).status_code == 202
    assert finished(client)["state"] == "completed"


def test_existing_synchronous_miner_keeps_its_slot(client, app_state):
    login(client, "miner")
    submit(client, 1)
    ledger = app_state.blockchain
    with ledger._miner:
        assert client.post("/api/mining", json={}).status_code == 202
        assert finished(client)["state"] == "busy"
    assert ledger.summary()["pending_count"] == 1
    assert client.post("/api/mining", json={}).status_code == 202
    complete = finished(client)
    assert complete["state"] == "completed"
    assert client.delete("/api/mining/" + complete["id"]).status_code == 409
