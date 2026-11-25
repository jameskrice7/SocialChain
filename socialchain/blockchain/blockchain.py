from itertools import chain, islice
from threading import Lock
from typing import List, Optional, Set

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from .block import Block
from .mining import MinerBusy
from .transaction import Transaction, TransactionType
from .crypto import merkle_root, hash_meets_difficulty


class DuplicateTransaction(ValueError):
    """The submitted ID is already pending or confirmed."""


class Blockchain:
    DIFFICULTY = 4

    def __init__(self):
        self._lock = Lock()
        self._miner = Lock()
        self._transaction_ids: Set[str] = set()
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = Block(index=0, transactions=[], previous_hash="0" * 64)
        genesis.nonce, genesis.hash = self._proof_of_work(genesis)
        self.chain.append(genesis)

    def _proof_of_work(self, block: Block, report=None):
        hash_nonce = block.nonce_hasher()
        target = "0" * self.DIFFICULTY
        first = 0
        while True:
            for nonce in range(first, first + 256):
                digest = hash_nonce(nonce)
                if digest.startswith(target):
                    if report:
                        report(nonce - first + 1)
                    return nonce, digest
            if report:
                report(256)
            first += 256

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: Transaction) -> int:
        with self._lock:
            if transaction.tx_id in self._transaction_ids:
                raise DuplicateTransaction(transaction.tx_id)
            if transaction.tx_type == TransactionType.MINING_REWARD:
                raise ValueError("Mining rewards are created by the miner")
            self._transaction_ids.add(transaction.tx_id)
            self.pending_transactions.append(transaction)
            return self.last_block.index + 1

    def verify_transaction(self, transaction: Transaction) -> bool:
        """Verify an ECDSA-signed transaction using the sender's public key.

        Returns True when:
        * the transaction carries a signature and the signature is valid, OR
        * the transaction has the format of an unsigned system mining reward.

        Returns False when the signature is missing or invalid.
        """
        if transaction.sender == "NETWORK":
            return transaction.is_mining_reward()
        if not transaction.signature:
            return False
        try:
            did_parts = transaction.sender.split(":")
            if len(did_parts) != 3 or did_parts[:2] != ["did", "socialchain"]:
                return False
            pub_hex = did_parts[2]
            pub_bytes = bytes.fromhex(pub_hex)
            public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256K1(), pub_bytes
            )
            sig_bytes = bytes.fromhex(transaction.signature)
            public_key.verify(sig_bytes, transaction.signing_payload(), ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError, TypeError, AttributeError):
            return False

    def mine_block(self, miner_did: str, *, require_pending: bool = False,
                   limit: Optional[int] = None, job=None) -> Optional[Block]:
        if limit is not None and (type(limit) is not int or limit < 1):
            raise ValueError("Batch size must be a positive integer")
        # Keep submissions and reads available during proof of work.
        if not self._miner.acquire(blocking=job is None):
            raise MinerBusy()
        try:
            while True:
                with self._lock:
                    pending = self.pending_transactions[:limit]
                    if require_pending and not pending:
                        return None
                    tip = self.last_block
                reward = Transaction(
                    sender="NETWORK", recipient=miner_did,
                    data={"reward": 1, "type": "mining_reward"},
                    tx_type=TransactionType.MINING_REWARD,
                )
                block = Block(tip.index + 1, pending + [reward], tip.hash)
                if job:
                    job.begin_candidate(block.index, len(pending))
                block.nonce, block.hash = self._proof_of_work(block, job.record if job else None)
                with self._lock:
                    if self.last_block is not tip or block.compute_hash() != block.hash:
                        continue
                    if job:
                        job.begin_commit()
                    self.chain.append(block)
                    self._transaction_ids.add(reward.tx_id)
                    del self.pending_transactions[:len(pending)]
                    return block
        finally:
            self._miner.release()

    def add_block(self, block: Block) -> bool:
        with self._lock:
            seen = {tx.tx_id for old in self.chain for tx in old.transactions}
            if not self._valid_block(block, len(self.chain), self.last_block.hash, seen):
                return False
            confirmed = {tx.tx_id for tx in block.transactions}
            self.pending_transactions = [
                tx for tx in self.pending_transactions if tx.tx_id not in confirmed
            ]
            self.chain.append(block)
            self._transaction_ids.update(confirmed)
            return True

    def _valid_block(self, block: Block, index: int, previous_hash: str, seen: Set[str]) -> bool:
        if (type(block.index) is not int or block.index != index
                or type(block.nonce) is not int or block.nonce < 0
                or block.previous_hash != previous_hash or block.hash != block.compute_hash()
                or not hash_meets_difficulty(block.hash, self.DIFFICULTY)):
            return False
        for position, tx in enumerate(block.transactions):
            if not isinstance(tx.tx_id, str) or not tx.tx_id or tx.tx_id in seen:
                return False
            seen.add(tx.tx_id)
            if tx.tx_type == TransactionType.MINING_REWARD:
                if position != len(block.transactions) - 1 or not tx.is_mining_reward():
                    return False
        return True

    def _valid_chain(self, blocks: List[Block]) -> bool:
        if not blocks or blocks[0].transactions:
            return False
        previous_hash = "0" * 64
        seen = set()
        for index, block in enumerate(blocks):
            if not self._valid_block(block, index, previous_hash, seen):
                return False
            previous_hash = block.hash
        return True

    def validate_chain(self) -> bool:
        with self._lock:
            return self._valid_chain(self.chain)

    def adopt_chain(self, blocks: List[Block]) -> bool:
        """Adopt a longer valid peer chain and return displaced work to the queue."""
        if len(blocks) <= len(self.chain) or not self._valid_chain(blocks):
            return False
        with self._lock:
            if len(blocks) <= len(self.chain):
                return False
            confirmed = {tx.tx_id for block in blocks for tx in block.transactions}
            displaced = (tx for block in self.chain for tx in block.transactions
                         if not tx.is_mining_reward())
            pending = []
            for tx in chain(displaced, self.pending_transactions):
                if tx.tx_id not in confirmed:
                    pending.append(tx)
                    confirmed.add(tx.tx_id)
            self.chain = list(blocks)
            self.pending_transactions = pending
            self._transaction_ids = confirmed
            return True

    def block_at(self, index: int) -> Optional[Block]:
        with self._lock:
            return self.chain[index] if 0 <= index < len(self.chain) else None

    def summary(self) -> dict:
        with self._lock:
            return {
                "length": len(self.chain),
                "pending_count": len(self.pending_transactions),
                "mined_count": len(self._transaction_ids) - len(self.pending_transactions),
                "recent_blocks": [
                    {"index": block.index, "hash": block.hash, "timestamp": block.timestamp,
                     "transaction_count": len(block.transactions)}
                    for block in reversed(self.chain[-12:])
                ],
            }

    def transaction_page(self, status: str, query: str, offset: int, limit: int) -> dict:
        """Return newest entries first within pending, then confirmed ledger order."""
        with self._lock:
            groups = []
            if status != "confirmed":
                groups.append((None, self.pending_transactions))
            blocks = () if status == "pending" else reversed(self.chain)
            confirmed = ((block, block.transactions) for block in blocks)
            entries = (
                (tx, block)
                for block, transactions in chain(groups, confirmed)
                for tx in reversed(transactions)
                if not query or any(query in str(field).casefold() for field in
                                    (tx.tx_id, tx.sender, tx.recipient, tx.tx_type))
            )
            page = list(islice(entries, offset, offset + limit + 1))
        return {
            "transactions": [
                {**tx.to_dict(), "block_index": block.index if block else None,
                 "block_hash": block.hash if block else None,
                 "signature_status": self.signature_status(tx)}
                for tx, block in page[:limit]
            ],
            "has_more": len(page) > limit,
        }

    def signature_status(self, tx: Transaction) -> str:
        if tx.is_mining_reward():
            return "system"
        if not tx.signature:
            return "unsigned"
        return "valid" if self.verify_transaction(tx) else "invalid"

    def pending_signatures(self) -> dict:
        with self._lock:
            transactions = list(self.pending_transactions)
        counts = {"valid": 0, "invalid": 0, "unsigned": 0, "system": 0}
        for tx in transactions:
            counts[self.signature_status(tx)] += 1
        return counts

    def get_balance(self, did: str) -> int:
        """Compute the balance (mining rewards received) for *did*."""
        return sum(1 for block in self.chain for tx in block.transactions
                   if tx.recipient == did and tx.is_mining_reward())

    def get_transactions_for(self, did: str) -> List[dict]:
        """Return all mined transactions involving *did* (as sender or recipient)."""
        results: List[dict] = []
        for block in self.chain:
            for tx in block.transactions:
                td = tx.to_dict() if isinstance(tx, Transaction) else tx
                if td.get("sender") == did or td.get("recipient") == did:
                    results.append(td)
        return results

    def get_merkle_root(self, block_index: int) -> str:
        """Return the Merkle root of transaction hashes for the given block."""
        if block_index < 0 or block_index >= len(self.chain):
            return "0" * 64
        block = self.chain[block_index]
        tx_hashes = [
            tx.compute_hash() if isinstance(tx, Transaction) else ""
            for tx in block.transactions
        ]
        return merkle_root(tx_hashes)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "chain": [block.to_dict() for block in self.chain],
                "length": len(self.chain),
                "pending_transactions": [tx.to_dict() for tx in self.pending_transactions],
            }

    def __repr__(self) -> str:
        return f"Blockchain(length={len(self.chain)}, pending={len(self.pending_transactions)})"
