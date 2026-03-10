"""Self-governing communities with membership management and rules.

Implements Shapiro's vision of self-sovereign communities where groups
define their own governance rules, membership criteria, and decision-making
processes without relying on central authorities.
"""
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from .proposal import Proposal, ProposalStatus
from .voting import VotingSystem, VotingMethod


class CommunityRole(str, Enum):
    MEMBER = "member"
    MODERATOR = "moderator"
    ADMIN = "admin"
    FOUNDER = "founder"


class Membership:
    """A membership record linking an identity to a community."""

    def __init__(self, did: str, community_id: str,
                 role: CommunityRole = CommunityRole.MEMBER,
                 joined_at: Optional[float] = None):
        self.did = did
        self.community_id = community_id
        self.role = CommunityRole(role)
        self.joined_at = joined_at or time.time()

    def to_dict(self) -> dict:
        return {
            "did": self.did,
            "community_id": self.community_id,
            "role": self.role.value,
            "joined_at": self.joined_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Membership":
        return cls(
            did=d["did"],
            community_id=d["community_id"],
            role=CommunityRole(d.get("role", "member")),
            joined_at=d.get("joined_at"),
        )


class Community:
    """A self-governing community with its own rules and governance structure.

    Each community defines:
    - Membership criteria (open, invite-only, vouch-required)
    - Voting method for proposals
    - Quorum and pass thresholds
    - Role-based permissions
    """

    def __init__(
        self,
        name: str,
        founder_did: str,
        description: str = "",
        voting_method: VotingMethod = VotingMethod.SIMPLE_MAJORITY,
        quorum_fraction: float = 0.5,
        pass_threshold: float = 0.5,
        community_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ):
        self.community_id = community_id or str(uuid.uuid4())
        self.name = name
        self.founder_did = founder_did
        self.description = description
        self.created_at = created_at or time.time()

        # Governance settings
        self.voting_system = VotingSystem(
            method=voting_method,
            quorum_fraction=quorum_fraction,
            pass_threshold=pass_threshold,
        )

        # Members: did -> Membership
        self._members: Dict[str, Membership] = {}
        # Add founder as first member
        self._members[founder_did] = Membership(
            founder_did, self.community_id, CommunityRole.FOUNDER
        )

        # Proposals: proposal_id -> Proposal
        self._proposals: Dict[str, Proposal] = {}

    def add_member(self, did: str, role: CommunityRole = CommunityRole.MEMBER) -> Membership:
        """Add a member to the community."""
        if did in self._members:
            raise ValueError("Already a member of this community")
        membership = Membership(did, self.community_id, role)
        self._members[did] = membership
        return membership

    def remove_member(self, did: str) -> bool:
        """Remove a member from the community."""
        if did not in self._members:
            return False
        if self._members[did].role == CommunityRole.FOUNDER:
            raise ValueError("Cannot remove the founder")
        del self._members[did]
        return True

    def get_member(self, did: str) -> Optional[Membership]:
        """Get a member's membership record."""
        return self._members.get(did)

    def is_member(self, did: str) -> bool:
        return did in self._members

    def list_members(self) -> List[Membership]:
        return list(self._members.values())

    def get_member_count(self) -> int:
        return len(self._members)

    def has_role(self, did: str, role: CommunityRole) -> bool:
        """Check if a member has at least the specified role level."""
        member = self._members.get(did)
        if not member:
            return False
        role_hierarchy = {
            CommunityRole.MEMBER: 0,
            CommunityRole.MODERATOR: 1,
            CommunityRole.ADMIN: 2,
            CommunityRole.FOUNDER: 3,
        }
        return role_hierarchy.get(member.role, 0) >= role_hierarchy.get(role, 0)

    def create_proposal(self, proposer_did: str, title: str,
                        description: str = "",
                        proposal_type: str = "custom",
                        parameters: Optional[Dict[str, Any]] = None) -> Proposal:
        """Create a new governance proposal."""
        if not self.is_member(proposer_did):
            raise ValueError("Only members can create proposals")

        proposal = Proposal(
            proposer_did=proposer_did,
            community_id=self.community_id,
            title=title,
            description=description,
            proposal_type=proposal_type,
            parameters=parameters,
        )
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def activate_proposal(self, proposal_id: str, activator_did: str) -> Proposal:
        """Activate a proposal for voting (requires moderator+ role)."""
        if not self.has_role(activator_did, CommunityRole.MODERATOR):
            raise ValueError("Requires moderator or higher role")
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")
        proposal.activate()
        return proposal

    def vote_on_proposal(self, proposal_id: str, voter_did: str,
                         choice: str, weight: float = 1.0) -> dict:
        """Cast a vote on an active proposal."""
        if not self.is_member(voter_did):
            raise ValueError("Only members can vote")

        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")
        if proposal.status != ProposalStatus.ACTIVE:
            raise ValueError("Proposal is not active for voting")

        vote = self.voting_system.cast_vote(voter_did, proposal_id, choice, weight)
        return vote.to_dict()

    def resolve_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Tally votes and resolve a proposal."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        tally = self.voting_system.tally_votes(
            proposal_id,
            eligible_voters=self.get_member_count()
        )
        proposal.resolve(tally["passed"])

        return {
            "proposal": proposal.to_dict(),
            "tally": tally,
        }

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        return self._proposals.get(proposal_id)

    def list_proposals(self, status: Optional[str] = None) -> List[Proposal]:
        proposals = list(self._proposals.values())
        if status:
            proposals = [p for p in proposals if p.status.value == status]
        return proposals

    def to_dict(self) -> dict:
        return {
            "community_id": self.community_id,
            "name": self.name,
            "founder_did": self.founder_did,
            "description": self.description,
            "member_count": self.get_member_count(),
            "proposal_count": len(self._proposals),
            "voting_method": self.voting_system.method.value,
            "quorum_fraction": self.voting_system.quorum_fraction,
            "pass_threshold": self.voting_system.pass_threshold,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Community":
        community = cls(
            name=d["name"],
            founder_did=d["founder_did"],
            description=d.get("description", ""),
            voting_method=VotingMethod(d.get("voting_method", "simple_majority")),
            quorum_fraction=d.get("quorum_fraction", 0.5),
            pass_threshold=d.get("pass_threshold", 0.5),
            community_id=d.get("community_id"),
            created_at=d.get("created_at"),
        )
        return community

    def __repr__(self) -> str:
        return f"Community(id={self.community_id[:8]}..., name={self.name!r}, members={self.get_member_count()})"
