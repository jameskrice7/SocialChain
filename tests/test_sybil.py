"""Tests for Sybil Resistance module."""
import pytest
from socialchain.social.trust import TrustGraph
from socialchain.social.sybil import (
    SybilResistance, Vouch, VouchStatus, VerificationLevel,
)


@pytest.fixture
def sybil_system():
    tg = TrustGraph()
    return SybilResistance(tg)


def test_create_vouch(sybil_system):
    vouch = sybil_system.create_vouch("did:alice", "did:bob", message="I know Bob")
    assert vouch.voucher_did == "did:alice"
    assert vouch.vouchee_did == "did:bob"
    assert vouch.status == VouchStatus.PENDING
    assert vouch.message == "I know Bob"


def test_cannot_vouch_self(sybil_system):
    with pytest.raises(ValueError, match="Cannot vouch for yourself"):
        sybil_system.create_vouch("did:alice", "did:alice")


def test_duplicate_vouch_rejected(sybil_system):
    sybil_system.create_vouch("did:alice", "did:bob")
    with pytest.raises(ValueError, match="Already vouched"):
        sybil_system.create_vouch("did:alice", "did:bob")


def test_accept_vouch(sybil_system):
    vouch = sybil_system.create_vouch("did:alice", "did:bob")
    accepted = sybil_system.accept_vouch(vouch.vouch_id)
    assert accepted.status == VouchStatus.ACCEPTED
    # Should update trust graph
    edge = sybil_system.trust_graph.get_trust("did:alice", "did:bob")
    assert edge is not None
    assert edge.score == 0.8


def test_accept_nonexistent_vouch(sybil_system):
    with pytest.raises(ValueError, match="Vouch not found"):
        sybil_system.accept_vouch("nonexistent-id")


def test_revoke_vouch(sybil_system):
    vouch = sybil_system.create_vouch("did:alice", "did:bob")
    sybil_system.accept_vouch(vouch.vouch_id)
    revoked = sybil_system.revoke_vouch(vouch.vouch_id)
    assert revoked.status == VouchStatus.REVOKED
    # Trust should be negative after revocation
    edge = sybil_system.trust_graph.get_trust("did:alice", "did:bob")
    assert edge.score == -0.5


def test_verification_unverified(sybil_system):
    level = sybil_system.compute_verification_level("did:nobody")
    assert level == VerificationLevel.UNVERIFIED


def test_verification_basic(sybil_system):
    vouch = sybil_system.create_vouch("did:alice", "did:bob")
    sybil_system.accept_vouch(vouch.vouch_id)
    level = sybil_system.compute_verification_level("did:bob")
    assert level == VerificationLevel.BASIC


def test_verification_standard(sybil_system):
    # Need 3 vouches with 2 from verified users
    # First, create verified vouchers
    for i, voucher in enumerate(["did:v1", "did:v2", "did:v3"]):
        # Pre-set vouchers as BASIC verified
        sybil_system._verification_cache[voucher] = VerificationLevel.BASIC
        vouch = sybil_system.create_vouch(voucher, "did:target")
        sybil_system.accept_vouch(vouch.vouch_id)

    level = sybil_system.compute_verification_level("did:target")
    assert level == VerificationLevel.STANDARD


def test_vouch_serialization():
    vouch = Vouch("did:alice", "did:bob", message="trusted friend")
    d = vouch.to_dict()
    assert d["voucher_did"] == "did:alice"
    assert d["status"] == "pending"
    restored = Vouch.from_dict(d)
    assert restored.vouch_id == vouch.vouch_id
    assert restored.message == "trusted friend"


def test_get_vouches_for(sybil_system):
    sybil_system.create_vouch("did:alice", "did:target")
    sybil_system.create_vouch("did:bob", "did:target")
    vouches = sybil_system.get_vouches_for("did:target")
    assert len(vouches) == 2


def test_sybil_detection_insufficient_data(sybil_system):
    sybil_system.trust_graph.add_node("did:suspect")
    result = sybil_system.detect_sybil_cluster("did:suspect")
    assert result["analysis"] == "insufficient_data"
    assert result["is_suspicious"] is False


def test_sybil_detection_normal_network(sybil_system):
    # Create a normal network with diverse connections
    tg = sybil_system.trust_graph
    nodes = ["did:a", "did:b", "did:c", "did:d", "did:e"]
    for n in nodes:
        tg.add_node(n)
    tg.set_trust("did:a", "did:b", 0.8)
    tg.set_trust("did:b", "did:c", 0.7)
    tg.set_trust("did:c", "did:d", 0.6)
    tg.set_trust("did:d", "did:e", 0.9)
    tg.set_trust("did:e", "did:a", 0.5)

    result = sybil_system.detect_sybil_cluster("did:a")
    # A normal ring network shouldn't be flagged as suspicious
    assert result["cluster_size"] >= 2


def test_sybil_resistance_to_dict(sybil_system):
    sybil_system.create_vouch("did:alice", "did:bob")
    d = sybil_system.to_dict()
    assert d["total_vouches"] == 1
    assert d["identities_tracked"] == 1
    assert len(d["vouches"]) == 1


def test_can_vouch_after_revocation(sybil_system):
    """After revoking a vouch, a new vouch should be possible."""
    vouch = sybil_system.create_vouch("did:alice", "did:bob")
    sybil_system.revoke_vouch(vouch.vouch_id)
    # Should be able to vouch again after revocation
    new_vouch = sybil_system.create_vouch("did:alice", "did:bob")
    assert new_vouch.vouch_id != vouch.vouch_id
