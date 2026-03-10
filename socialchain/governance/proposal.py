"""Governance proposals for community decision-making.

Proposals are formal requests for community action, following Shapiro's model
of structured digital democracy where every participant can propose changes
and the community votes according to agreed-upon rules.
"""
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class ProposalType(str, Enum):
    POLICY_CHANGE = "policy_change"
    MEMBERSHIP = "membership"
    RESOURCE_ALLOCATION = "resource_allocation"
    PARAMETER_CHANGE = "parameter_change"
    CUSTOM = "custom"


class Proposal:
    """A governance proposal submitted for community voting."""

    DEFAULT_VOTING_PERIOD = 86400 * 7  # 7 days in seconds

    def __init__(
        self,
        proposer_did: str,
        community_id: str,
        title: str,
        description: str = "",
        proposal_type: ProposalType = ProposalType.CUSTOM,
        parameters: Optional[Dict[str, Any]] = None,
        voting_period: Optional[float] = None,
        proposal_id: Optional[str] = None,
        status: ProposalStatus = ProposalStatus.DRAFT,
        created_at: Optional[float] = None,
    ):
        self.proposal_id = proposal_id or str(uuid.uuid4())
        self.proposer_did = proposer_did
        self.community_id = community_id
        self.title = title
        self.description = description
        self.proposal_type = ProposalType(proposal_type)
        self.parameters = parameters or {}
        self.voting_period = voting_period or self.DEFAULT_VOTING_PERIOD
        self.status = ProposalStatus(status)
        self.created_at = created_at or time.time()
        self.activated_at: Optional[float] = None
        self.resolved_at: Optional[float] = None

    def activate(self) -> None:
        """Move proposal from draft to active voting status."""
        if self.status != ProposalStatus.DRAFT:
            raise ValueError(f"Cannot activate proposal in {self.status.value} status")
        self.status = ProposalStatus.ACTIVE
        self.activated_at = time.time()

    def resolve(self, passed: bool) -> None:
        """Resolve the proposal based on voting results."""
        if self.status != ProposalStatus.ACTIVE:
            raise ValueError(f"Cannot resolve proposal in {self.status.value} status")
        self.status = ProposalStatus.PASSED if passed else ProposalStatus.REJECTED
        self.resolved_at = time.time()

    def execute(self) -> None:
        """Mark a passed proposal as executed."""
        if self.status != ProposalStatus.PASSED:
            raise ValueError(f"Cannot execute proposal in {self.status.value} status")
        self.status = ProposalStatus.EXECUTED

    def is_voting_expired(self) -> bool:
        """Check if the voting period has expired."""
        if self.activated_at is None:
            return False
        return time.time() > (self.activated_at + self.voting_period)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "proposer_did": self.proposer_did,
            "community_id": self.community_id,
            "title": self.title,
            "description": self.description,
            "proposal_type": self.proposal_type.value,
            "parameters": self.parameters,
            "voting_period": self.voting_period,
            "status": self.status.value,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Proposal":
        proposal = cls(
            proposer_did=d["proposer_did"],
            community_id=d["community_id"],
            title=d["title"],
            description=d.get("description", ""),
            proposal_type=ProposalType(d.get("proposal_type", "custom")),
            parameters=d.get("parameters", {}),
            voting_period=d.get("voting_period"),
            proposal_id=d.get("proposal_id"),
            status=ProposalStatus(d.get("status", "draft")),
            created_at=d.get("created_at"),
        )
        proposal.activated_at = d.get("activated_at")
        proposal.resolved_at = d.get("resolved_at")
        return proposal

    def __repr__(self) -> str:
        return f"Proposal(id={self.proposal_id[:8]}..., title={self.title!r}, status={self.status.value})"
