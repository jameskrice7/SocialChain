import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class RequestAction(str, Enum):
    REQUEST_FEATURE = "REQUEST_FEATURE"
    CHANGE_FEATURE = "CHANGE_FEATURE"
    DEPLOY_AGENT = "DEPLOY_AGENT"
    SEND_MESSAGE = "SEND_MESSAGE"


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SocialRequest:
    def __init__(
        self,
        requester_did: str,
        target_did: str,
        action: RequestAction,
        payload: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        status: RequestStatus = RequestStatus.PENDING,
        created_at: Optional[str] = None,
    ):
        self.request_id = request_id or str(uuid.uuid4())
        self.requester_did = requester_did
        self.target_did = target_did
        self.action = RequestAction(action)
        self.payload = payload or {}
        self.status = RequestStatus(status)
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "requester_did": self.requester_did,
            "target_did": self.target_did,
            "action": self.action.value,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SocialRequest":
        return cls(
            requester_did=d["requester_did"],
            target_did=d["target_did"],
            action=RequestAction(d["action"]),
            payload=d.get("payload", {}),
            request_id=d.get("request_id"),
            status=RequestStatus(d.get("status", "PENDING")),
            created_at=d.get("created_at"),
        )

    def __repr__(self) -> str:
        return f"SocialRequest(id={self.request_id[:8]}..., action={self.action}, status={self.status})"
