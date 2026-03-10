"""Tests for Governance module (proposals, voting, communities)."""
import pytest
from socialchain.governance.proposal import Proposal, ProposalStatus, ProposalType
from socialchain.governance.voting import VotingSystem, VoteChoice, VotingMethod, Vote
from socialchain.governance.community import Community, CommunityRole, Membership


# ── Proposal Tests ───────────────────────────────────────────────────────────

def test_proposal_creation():
    p = Proposal(
        proposer_did="did:alice",
        community_id="comm-1",
        title="Test Proposal",
        description="A test",
        proposal_type=ProposalType.POLICY_CHANGE,
    )
    assert p.proposer_did == "did:alice"
    assert p.title == "Test Proposal"
    assert p.status == ProposalStatus.DRAFT
    assert p.proposal_id is not None


def test_proposal_lifecycle():
    p = Proposal(proposer_did="did:alice", community_id="c1", title="Lifecycle")
    assert p.status == ProposalStatus.DRAFT

    p.activate()
    assert p.status == ProposalStatus.ACTIVE
    assert p.activated_at is not None

    p.resolve(passed=True)
    assert p.status == ProposalStatus.PASSED

    p.execute()
    assert p.status == ProposalStatus.EXECUTED


def test_proposal_rejected():
    p = Proposal(proposer_did="did:alice", community_id="c1", title="Rejected")
    p.activate()
    p.resolve(passed=False)
    assert p.status == ProposalStatus.REJECTED


def test_proposal_cannot_activate_twice():
    p = Proposal(proposer_did="did:alice", community_id="c1", title="Double Activate")
    p.activate()
    with pytest.raises(ValueError):
        p.activate()


def test_proposal_cannot_execute_if_not_passed():
    p = Proposal(proposer_did="did:alice", community_id="c1", title="No Execute")
    p.activate()
    p.resolve(passed=False)
    with pytest.raises(ValueError):
        p.execute()


def test_proposal_serialization():
    p = Proposal(
        proposer_did="did:alice",
        community_id="c1",
        title="Serialize",
        proposal_type=ProposalType.MEMBERSHIP,
        parameters={"target": "did:bob"},
    )
    d = p.to_dict()
    assert d["title"] == "Serialize"
    assert d["proposal_type"] == "membership"
    assert d["parameters"]["target"] == "did:bob"

    restored = Proposal.from_dict(d)
    assert restored.proposal_id == p.proposal_id
    assert restored.proposal_type == ProposalType.MEMBERSHIP


# ── Voting System Tests ──────────────────────────────────────────────────────

def test_simple_majority_vote():
    vs = VotingSystem(method=VotingMethod.SIMPLE_MAJORITY)
    vs.cast_vote("did:alice", "p1", VoteChoice.FOR)
    vs.cast_vote("did:bob", "p1", VoteChoice.FOR)
    vs.cast_vote("did:carol", "p1", VoteChoice.AGAINST)

    tally = vs.tally_votes("p1")
    assert tally["votes_for"] == 2.0
    assert tally["votes_against"] == 1.0
    assert tally["passed"] is True


def test_simple_majority_fails():
    vs = VotingSystem(method=VotingMethod.SIMPLE_MAJORITY)
    vs.cast_vote("did:alice", "p1", VoteChoice.AGAINST)
    vs.cast_vote("did:bob", "p1", VoteChoice.AGAINST)
    vs.cast_vote("did:carol", "p1", VoteChoice.FOR)

    tally = vs.tally_votes("p1")
    assert tally["passed"] is False


def test_double_vote_rejected():
    vs = VotingSystem()
    vs.cast_vote("did:alice", "p1", VoteChoice.FOR)
    with pytest.raises(ValueError, match="Already voted"):
        vs.cast_vote("did:alice", "p1", VoteChoice.AGAINST)


def test_quadratic_voting():
    vs = VotingSystem(method=VotingMethod.QUADRATIC)
    # With quadratic voting, weight 4 -> sqrt(4) = 2.0 effective weight
    vs.cast_vote("did:alice", "p1", VoteChoice.FOR, weight=4.0)
    vs.cast_vote("did:bob", "p1", VoteChoice.AGAINST, weight=1.0)

    tally = vs.tally_votes("p1")
    assert tally["votes_for"] == 2.0  # sqrt(4)
    assert tally["votes_against"] == 1.0  # sqrt(1)
    assert tally["passed"] is True


def test_quorum_not_met():
    vs = VotingSystem(quorum_fraction=0.5)
    vs.cast_vote("did:alice", "p1", VoteChoice.FOR)

    # 1 voter out of 10 eligible = 10% < 50% quorum
    tally = vs.tally_votes("p1", eligible_voters=10)
    assert tally["has_quorum"] is False
    assert tally["passed"] is False


def test_delegated_voting():
    vs = VotingSystem(method=VotingMethod.DELEGATED)
    # Alice delegates to Bob
    vs.delegate_vote("did:alice", "did:bob")
    # Bob votes FOR
    vs.cast_vote("did:bob", "p1", VoteChoice.FOR)
    # Alice also "casts" but should follow Bob's effective vote
    vs.cast_vote("did:alice", "p1", VoteChoice.AGAINST)

    tally = vs.tally_votes("p1")
    # Delegation should cause Alice's vote to follow Bob
    assert tally["voter_count"] == 2


def test_circular_delegation_prevented():
    vs = VotingSystem(method=VotingMethod.DELEGATED)
    vs.delegate_vote("did:alice", "did:bob")
    vs.delegate_vote("did:bob", "did:carol")
    with pytest.raises(ValueError, match="Circular delegation"):
        vs.delegate_vote("did:carol", "did:alice")


def test_remove_delegation():
    vs = VotingSystem(method=VotingMethod.DELEGATED)
    vs.delegate_vote("did:alice", "did:bob")
    vs.remove_delegation("did:alice")
    assert vs.get_effective_voter("did:alice") == "did:alice"


def test_has_voted():
    vs = VotingSystem()
    assert vs.has_voted("did:alice", "p1") is False
    vs.cast_vote("did:alice", "p1", VoteChoice.FOR)
    assert vs.has_voted("did:alice", "p1") is True


def test_voting_system_serialization():
    vs = VotingSystem(method=VotingMethod.QUADRATIC, quorum_fraction=0.3)
    d = vs.to_dict()
    assert d["method"] == "quadratic"
    assert d["quorum_fraction"] == 0.3


# ── Community Tests ──────────────────────────────────────────────────────────

def test_community_creation():
    c = Community(name="Test Community", founder_did="did:alice")
    assert c.name == "Test Community"
    assert c.founder_did == "did:alice"
    assert c.get_member_count() == 1  # Founder auto-added
    assert c.is_member("did:alice")


def test_community_add_member():
    c = Community(name="Test", founder_did="did:alice")
    m = c.add_member("did:bob")
    assert m.role == CommunityRole.MEMBER
    assert c.get_member_count() == 2


def test_community_duplicate_member():
    c = Community(name="Test", founder_did="did:alice")
    with pytest.raises(ValueError, match="Already a member"):
        c.add_member("did:alice")


def test_community_remove_member():
    c = Community(name="Test", founder_did="did:alice")
    c.add_member("did:bob")
    assert c.remove_member("did:bob") is True
    assert c.is_member("did:bob") is False


def test_community_cannot_remove_founder():
    c = Community(name="Test", founder_did="did:alice")
    with pytest.raises(ValueError, match="Cannot remove the founder"):
        c.remove_member("did:alice")


def test_community_role_hierarchy():
    c = Community(name="Test", founder_did="did:alice")
    c.add_member("did:bob", CommunityRole.MODERATOR)
    c.add_member("did:carol")

    assert c.has_role("did:alice", CommunityRole.FOUNDER)
    assert c.has_role("did:alice", CommunityRole.ADMIN)  # Founder >= Admin
    assert c.has_role("did:bob", CommunityRole.MODERATOR)
    assert not c.has_role("did:carol", CommunityRole.MODERATOR)
    assert c.has_role("did:carol", CommunityRole.MEMBER)


def test_community_proposal_workflow():
    c = Community(name="Test", founder_did="did:alice")
    c.add_member("did:bob")
    c.add_member("did:carol")

    # Create proposal
    p = c.create_proposal("did:bob", "Add new feature", description="A great idea")
    assert p.status == ProposalStatus.DRAFT

    # Activate (founder has moderator+ role)
    c.activate_proposal(p.proposal_id, "did:alice")
    assert p.status == ProposalStatus.ACTIVE

    # Vote
    c.vote_on_proposal(p.proposal_id, "did:alice", VoteChoice.FOR)
    c.vote_on_proposal(p.proposal_id, "did:bob", VoteChoice.FOR)
    c.vote_on_proposal(p.proposal_id, "did:carol", VoteChoice.AGAINST)

    # Resolve
    result = c.resolve_proposal(p.proposal_id)
    assert result["tally"]["passed"] is True
    assert p.status == ProposalStatus.PASSED


def test_community_non_member_cannot_propose():
    c = Community(name="Test", founder_did="did:alice")
    with pytest.raises(ValueError, match="Only members"):
        c.create_proposal("did:outsider", "Bad proposal")


def test_community_non_member_cannot_vote():
    c = Community(name="Test", founder_did="did:alice")
    c.add_member("did:bob")
    p = c.create_proposal("did:alice", "Test")
    c.activate_proposal(p.proposal_id, "did:alice")
    with pytest.raises(ValueError, match="Only members can vote"):
        c.vote_on_proposal(p.proposal_id, "did:outsider", VoteChoice.FOR)


def test_community_serialization():
    c = Community(
        name="Serialize Test",
        founder_did="did:alice",
        description="A test community",
        voting_method=VotingMethod.QUADRATIC,
    )
    d = c.to_dict()
    assert d["name"] == "Serialize Test"
    assert d["voting_method"] == "quadratic"
    assert d["member_count"] == 1

    restored = Community.from_dict(d)
    assert restored.name == c.name
    assert restored.community_id == c.community_id


def test_membership_serialization():
    m = Membership(did="did:alice", community_id="c1", role=CommunityRole.ADMIN)
    d = m.to_dict()
    assert d["role"] == "admin"
    restored = Membership.from_dict(d)
    assert restored.role == CommunityRole.ADMIN


def test_community_list_proposals_with_filter():
    c = Community(name="Test", founder_did="did:alice")
    p1 = c.create_proposal("did:alice", "Draft Proposal")
    p2 = c.create_proposal("did:alice", "Active Proposal")
    c.activate_proposal(p2.proposal_id, "did:alice")

    draft_proposals = c.list_proposals(status="draft")
    assert len(draft_proposals) == 1
    assert draft_proposals[0].title == "Draft Proposal"

    active_proposals = c.list_proposals(status="active")
    assert len(active_proposals) == 1
    assert active_proposals[0].title == "Active Proposal"

    all_proposals = c.list_proposals()
    assert len(all_proposals) == 2
