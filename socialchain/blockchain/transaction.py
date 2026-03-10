import hashlib
import json
import time
import uuid
from typing import Any, Optional


class TransactionType:
    """Well-known transaction type constants."""
    TRANSFER = "transfer"
    MINING_REWARD = "mining_reward"
    REGISTRATION = "registration"
    PROFILE_UPDATE = "profile_update"
    CONNECTION = "connection"
    CONTRACT_DEPLOY = "contract_deploy"
    CONTRACT_EXEC = "contract_exec"
    AGENT_REGISTRATION = "agent_registration"
    AGENT_TASK = "agent_task"
    AGENT_STATUS = "agent_status"
    GOVERNANCE = "governance"
    AGENT_ACTION = "agent_action"


class Transaction:
    def __init__(
        self,
        sender: str,
        recipient: str,
        data: Any,
        signature: Optional[str] = None,
        tx_id: Optional[str] = None,
        tx_type: Optional[str] = None,
        timestamp: Optional[float] = None,
    ):
        self.sender = sender
        self.recipient = recipient
        self.data = data
        self.signature = signature
        self.tx_id = tx_id or str(uuid.uuid4())
        self.tx_type = tx_type or self._infer_type()
        self.timestamp = timestamp if timestamp is not None else time.time()

    def _infer_type(self) -> str:
        """Best-effort inference of tx_type from data payload."""
        if isinstance(self.data, dict):
            t = self.data.get("type", "")
            if t in vars(TransactionType).values():
                return t
            if "reward" in self.data:
                return TransactionType.MINING_REWARD
        return TransactionType.TRANSFER

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "data": self.data,
            "signature": self.signature,
            "tx_type": self.tx_type,
            "timestamp": self.timestamp,
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
            tx_type=d.get("tx_type"),
            timestamp=d.get("timestamp"),
        )

    def __repr__(self) -> str:
        return f"Transaction(tx_id={self.tx_id}, sender={self.sender[:16]}..., recipient={self.recipient[:16]}...)"
