import hashlib
import json
import uuid
from typing import Any, Optional


class Transaction:
    def __init__(
        self,
        sender: str,
        recipient: str,
        data: Any,
        signature: Optional[str] = None,
        tx_id: Optional[str] = None,
    ):
        self.sender = sender
        self.recipient = recipient
        self.data = data
        self.signature = signature
        self.tx_id = tx_id or str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "data": self.data,
            "signature": self.signature,
        }

    def compute_hash(self) -> str:
        tx_string = json.dumps(
            {"sender": self.sender, "recipient": self.recipient, "data": self.data},
            sort_keys=True,
        )
        return hashlib.sha256(tx_string.encode()).hexdigest()

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(
            sender=d["sender"],
            recipient=d["recipient"],
            data=d["data"],
            signature=d.get("signature"),
            tx_id=d.get("tx_id"),
        )

    def __repr__(self) -> str:
        return f"Transaction(tx_id={self.tx_id}, sender={self.sender[:16]}..., recipient={self.recipient[:16]}...)"
