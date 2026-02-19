import pytest
from socialchain.blockchain import Block, Transaction, Blockchain, Identity


def test_transaction_creation():
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    assert tx.sender == "alice"
    assert tx.recipient == "bob"
    assert tx.data == {"amount": 10}
    assert tx.tx_id is not None


def test_transaction_to_dict():
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    d = tx.to_dict()
    assert d["sender"] == "alice"
    assert d["recipient"] == "bob"
    assert d["data"] == {"amount": 10}


def test_transaction_from_dict():
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    d = tx.to_dict()
    tx2 = Transaction.from_dict(d)
    assert tx2.sender == tx.sender
    assert tx2.recipient == tx.recipient
    assert tx2.tx_id == tx.tx_id


def test_block_creation():
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    block = Block(index=1, transactions=[tx], previous_hash="0" * 64)
    assert block.index == 1
    assert len(block.transactions) == 1
    assert block.hash is not None


def test_block_compute_hash():
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    block = Block(index=1, transactions=[tx], previous_hash="0" * 64)
    h1 = block.compute_hash()
    h2 = block.compute_hash()
    assert h1 == h2


def test_blockchain_genesis():
    bc = Blockchain()
    assert len(bc.chain) == 1
    assert bc.chain[0].index == 0
    assert bc.chain[0].previous_hash == "0" * 64


def test_blockchain_mine_block():
    bc = Blockchain()
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    bc.add_transaction(tx)
    block = bc.mine_block("did:socialchain:miner")
    assert block.index == 1
    assert block.hash.startswith("0" * Blockchain.DIFFICULTY)
    assert len(bc.pending_transactions) == 0


def test_blockchain_validate_chain():
    bc = Blockchain()
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    bc.add_transaction(tx)
    bc.mine_block("did:socialchain:miner")
    assert bc.validate_chain() is True


def test_blockchain_invalid_chain():
    bc = Blockchain()
    tx = Transaction(sender="alice", recipient="bob", data={"amount": 10})
    bc.add_transaction(tx)
    bc.mine_block("did:socialchain:miner")
    # Tamper with the chain
    bc.chain[1].transactions[0].data = {"amount": 9999}
    bc.chain[1].hash = bc.chain[1].compute_hash()
    assert bc.validate_chain() is False


def test_identity_creation():
    identity = Identity()
    assert identity.did.startswith("did:socialchain:")
    assert len(identity.public_key_hex()) > 0


def test_identity_sign_verify():
    identity = Identity()
    message = b"hello socialchain"
    signature = identity.sign(message)
    assert identity.verify(message, signature) is True
    assert identity.verify(b"wrong message", signature) is False


def test_identity_did_format():
    identity = Identity()
    parts = identity.did.split(":")
    assert len(parts) == 3
    assert parts[0] == "did"
    assert parts[1] == "socialchain"
    assert len(parts[2]) > 0
