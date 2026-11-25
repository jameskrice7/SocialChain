import hashlib
import json
import time
from typing import List, Optional
from .transaction import Transaction


class Block:
    def __init__(
        self,
        index: int,
        transactions: List[Transaction],
        previous_hash: str,
        nonce: int = 0,
        timestamp: Optional[float] = None,
    ):
        self.index = index
        self.timestamp = time.time() if timestamp is None else timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        block_dict = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_dict, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, record: dict) -> "Block":
        block = cls(
            index=record["index"],
            transactions=[Transaction.from_dict(tx) for tx in record["transactions"]],
            previous_hash=record["previous_hash"],
            nonce=record["nonce"],
            timestamp=record["timestamp"],
        )
        if block.hash != record["hash"]:
            raise ValueError("Block hash does not match its contents")
        return block

    def __repr__(self) -> str:
        return f"Block(index={self.index}, hash={self.hash[:16]}..., txs={len(self.transactions)})"
