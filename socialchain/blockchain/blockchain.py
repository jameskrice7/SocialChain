import json
from typing import Dict, List, Optional
from .block import Block
from .transaction import Transaction, TransactionType
from .crypto import merkle_root, hash_meets_difficulty


class Blockchain:
    DIFFICULTY = 4

    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = Block(index=0, transactions=[], previous_hash="0" * 64)
        genesis.nonce, genesis.hash = self._proof_of_work(genesis)
        self.chain.append(genesis)

    def _proof_of_work(self, block: Block):
        nonce = 0
        block.nonce = nonce
        computed = block.compute_hash()
        while not hash_meets_difficulty(computed, self.DIFFICULTY):
            nonce += 1
            block.nonce = nonce
            computed = block.compute_hash()
        return nonce, computed

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: Transaction) -> int:
        self.pending_transactions.append(transaction)
        return self.last_block.index + 1

    def verify_transaction(self, transaction: Transaction) -> bool:
        """Verify an ECDSA-signed transaction using the sender's public key.

        Returns True when:
        * the transaction carries a signature and the signature is valid, OR
        * the sender is ``NETWORK`` (mining reward / system tx).

        Returns False when the signature is missing or invalid.
        """
        if transaction.sender == "NETWORK":
            return True
        if not transaction.signature:
            return False
        try:
            from .identity import Identity
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.backends import default_backend

            did_parts = transaction.sender.split(":")
            if len(did_parts) != 3 or did_parts[0] != "did":
                return False
            pub_hex = did_parts[2]
            pub_bytes = bytes.fromhex(pub_hex)
            public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256K1(), pub_bytes
            )
            payload = json.dumps(transaction.to_dict(), sort_keys=True).encode()
            sig_bytes = bytes.fromhex(transaction.signature)
            public_key.verify(sig_bytes, payload, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False

    def mine_block(self, miner_did: str) -> Block:
        reward_tx = Transaction(
            sender="NETWORK",
            recipient=miner_did,
            data={"reward": 1, "type": "mining_reward"},
            tx_type=TransactionType.MINING_REWARD,
        )
        self.pending_transactions.append(reward_tx)
        block = Block(
            index=len(self.chain),
            transactions=list(self.pending_transactions),
            previous_hash=self.last_block.hash,
        )
        nonce, block_hash = self._proof_of_work(block)
        block.nonce = nonce
        block.hash = block_hash
        self.chain.append(block)
        self.pending_transactions = []
        return block

    def add_block(self, block: Block) -> bool:
        if block.previous_hash != self.last_block.hash:
            return False
        if not hash_meets_difficulty(block.hash, self.DIFFICULTY):
            return False
        if block.hash != block.compute_hash():
            return False
        self.chain.append(block)
        return True

    def validate_chain(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not hash_meets_difficulty(current.hash, self.DIFFICULTY):
                return False
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_balance(self, did: str) -> int:
        """Compute the balance (mining rewards received) for *did*."""
        balance = 0
        for block in self.chain:
            for tx in block.transactions:
                if isinstance(tx, Transaction):
                    if tx.recipient == did and isinstance(tx.data, dict) and "reward" in tx.data:
                        balance += tx.data["reward"]
        return balance

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
        return {
            "chain": [block.to_dict() for block in self.chain],
            "length": len(self.chain),
            "pending_transactions": [tx.to_dict() for tx in self.pending_transactions],
        }

    def __repr__(self) -> str:
        return f"Blockchain(length={len(self.chain)}, pending={len(self.pending_transactions)})"
