import hashlib
import json
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional


class ContractStatus(Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class SmartContract:
    """A contract between participants, anchored to the SocialChain blockchain."""

    def __init__(
        self,
        creator_did: str,
        title: str,
        description: str = "",
        participants: Optional[List[str]] = None,
        terms: Optional[Dict[str, Any]] = None,
        contract_id: Optional[str] = None,
    ):
        self.contract_id = contract_id or str(uuid.uuid4())
        self.creator_did = creator_did
        self.title = title
        self.description = description
        self.participants = participants or []
        self.terms = terms or {}
        self.status = ContractStatus.PENDING
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.tx_ids: List[str] = []
        self.completion_data: Optional[Dict] = None

    def compute_hash(self) -> str:
        contract_str = json.dumps(
            {
                "contract_id": self.contract_id,
                "creator_did": self.creator_did,
                "title": self.title,
                "terms": self.terms,
            },
            sort_keys=True,
        )
        return hashlib.sha256(contract_str.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "creator_did": self.creator_did,
            "title": self.title,
            "description": self.description,
            "participants": self.participants,
            "terms": self.terms,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tx_ids": self.tx_ids,
            "completion_data": self.completion_data,
            "contract_hash": self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SmartContract":
        contract = cls(
            creator_did=d["creator_did"],
            title=d["title"],
            description=d.get("description", ""),
            participants=d.get("participants", []),
            terms=d.get("terms", {}),
            contract_id=d.get("contract_id"),
        )
        if "status" in d:
            contract.status = ContractStatus(d["status"])
        if "created_at" in d:
            contract.created_at = d["created_at"]
        if "updated_at" in d:
            contract.updated_at = d["updated_at"]
        if "tx_ids" in d:
            contract.tx_ids = d["tx_ids"]
        if "completion_data" in d:
            contract.completion_data = d["completion_data"]
        return contract

    def __repr__(self) -> str:
        return f"SmartContract(id={self.contract_id[:8]}…, title={self.title!r}, status={self.status.value})"
