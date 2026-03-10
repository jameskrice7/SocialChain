"""Voting system supporting multiple democratic mechanisms.

Implements voting methods inspired by Shapiro's digital democracy research:
- Simple majority: one-person-one-vote with majority threshold
- Quadratic voting: cost of votes grows quadratically, preventing plutocracy
- Delegated voting: liquid democracy where votes can be delegated to trusted peers

These mechanisms ensure fair representation while preventing concentration of power.
"""
import math
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class VoteChoice(str, Enum):
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"


class VotingMethod(str, Enum):
    SIMPLE_MAJORITY = "simple_majority"
    QUADRATIC = "quadratic"
    DELEGATED = "delegated"


class Vote:
    """An individual vote cast on a proposal."""

    def __init__(self, voter_did: str, proposal_id: str, choice: VoteChoice,
                 weight: float = 1.0, timestamp: Optional[float] = None):
        self.voter_did = voter_did
        self.proposal_id = proposal_id
        self.choice = VoteChoice(choice)
        self.weight = weight
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "voter_did": self.voter_did,
            "proposal_id": self.proposal_id,
            "choice": self.choice.value,
            "weight": self.weight,
            "timestamp": self.timestamp,
        }


class VotingSystem:
    """Manages voting on proposals with configurable voting methods."""

    def __init__(self, method: VotingMethod = VotingMethod.SIMPLE_MAJORITY,
                 quorum_fraction: float = 0.5, pass_threshold: float = 0.5):
        self.method = VotingMethod(method)
        self.quorum_fraction = quorum_fraction
        self.pass_threshold = pass_threshold
        # proposal_id -> {voter_did -> Vote}
        self._votes: Dict[str, Dict[str, Vote]] = {}
        # voter_did -> delegate_did (for delegated voting)
        self._delegations: Dict[str, str] = {}

    def cast_vote(self, voter_did: str, proposal_id: str,
                  choice: VoteChoice, weight: float = 1.0) -> Vote:
        """Cast a vote on a proposal."""
        if proposal_id not in self._votes:
            self._votes[proposal_id] = {}

        if voter_did in self._votes[proposal_id]:
            raise ValueError("Already voted on this proposal")

        effective_weight = weight
        if self.method == VotingMethod.QUADRATIC:
            # In quadratic voting, the cost is the square of the votes
            # So effective voting power is sqrt of credits spent
            effective_weight = math.sqrt(abs(weight))

        vote = Vote(voter_did, proposal_id, choice, effective_weight)
        self._votes[proposal_id][voter_did] = vote
        return vote

    def delegate_vote(self, delegator_did: str, delegate_did: str) -> None:
        """Delegate voting power to another identity (liquid democracy)."""
        if delegator_did == delegate_did:
            raise ValueError("Cannot delegate to yourself")

        # Prevent circular delegation
        current = delegate_did
        visited = {delegator_did}
        while current in self._delegations:
            if current in visited:
                raise ValueError("Circular delegation detected")
            visited.add(current)
            current = self._delegations[current]
        if current in visited:
            raise ValueError("Circular delegation detected")

        self._delegations[delegator_did] = delegate_did

    def remove_delegation(self, delegator_did: str) -> None:
        """Remove a vote delegation."""
        self._delegations.pop(delegator_did, None)

    def get_effective_voter(self, voter_did: str) -> str:
        """Resolve delegation chain to find the effective voter."""
        current = voter_did
        visited = set()
        while current in self._delegations:
            if current in visited:
                return current  # Break circular delegation
            visited.add(current)
            current = self._delegations[current]
        return current

    def tally_votes(self, proposal_id: str,
                    eligible_voters: int = 0) -> Dict[str, Any]:
        """Tally votes for a proposal and determine the outcome."""
        votes = self._votes.get(proposal_id, {})

        # Aggregate votes with delegation support
        effective_votes: Dict[str, float] = {
            VoteChoice.FOR.value: 0.0,
            VoteChoice.AGAINST.value: 0.0,
            VoteChoice.ABSTAIN.value: 0.0,
        }

        processed_voters = set()
        for voter_did, vote in votes.items():
            if self.method == VotingMethod.DELEGATED:
                effective_voter = self.get_effective_voter(voter_did)
                if effective_voter in processed_voters:
                    continue
                processed_voters.add(effective_voter)
                # Check if the effective voter actually voted
                if effective_voter in votes:
                    effective_vote = votes[effective_voter]
                    effective_votes[effective_vote.choice.value] += effective_vote.weight
                else:
                    effective_votes[vote.choice.value] += vote.weight
            else:
                effective_votes[vote.choice.value] += vote.weight

        total_cast = sum(effective_votes.values())
        votes_for = effective_votes[VoteChoice.FOR.value]
        votes_against = effective_votes[VoteChoice.AGAINST.value]

        # Check quorum
        has_quorum = True
        if eligible_voters > 0:
            has_quorum = total_cast >= (eligible_voters * self.quorum_fraction)

        # Determine if passed
        decisive_votes = votes_for + votes_against
        passed = False
        if decisive_votes > 0 and has_quorum:
            passed = (votes_for / decisive_votes) > self.pass_threshold

        return {
            "proposal_id": proposal_id,
            "votes_for": votes_for,
            "votes_against": votes_against,
            "votes_abstain": effective_votes[VoteChoice.ABSTAIN.value],
            "total_votes_cast": total_cast,
            "voter_count": len(votes),
            "has_quorum": has_quorum,
            "passed": passed,
            "method": self.method.value,
        }

    def get_votes(self, proposal_id: str) -> List[Vote]:
        """Get all votes cast on a proposal."""
        return list(self._votes.get(proposal_id, {}).values())

    def has_voted(self, voter_did: str, proposal_id: str) -> bool:
        """Check if a voter has already voted on a proposal."""
        return voter_did in self._votes.get(proposal_id, {})

    def to_dict(self) -> dict:
        return {
            "method": self.method.value,
            "quorum_fraction": self.quorum_fraction,
            "pass_threshold": self.pass_threshold,
            "total_proposals_voted": len(self._votes),
            "active_delegations": len(self._delegations),
        }
