"""Tests for Trust & Reputation system."""
import pytest
from socialchain.social.trust import (
    TrustGraph, TrustEdge, TrustLevel, score_to_trust_level,
)


def test_trust_level_thresholds():
    assert score_to_trust_level(-0.5) == TrustLevel.DISTRUSTED
    assert score_to_trust_level(0.0) == TrustLevel.UNKNOWN
    assert score_to_trust_level(0.3) == TrustLevel.LOW
    assert score_to_trust_level(0.5) == TrustLevel.MEDIUM
    assert score_to_trust_level(0.8) == TrustLevel.HIGH
    assert score_to_trust_level(0.95) == TrustLevel.VOUCHED


def test_trust_edge_creation():
    edge = TrustEdge("did:a", "did:b", 0.8, context="trade")
    assert edge.truster_did == "did:a"
    assert edge.trustee_did == "did:b"
    assert edge.score == 0.8
    assert edge.context == "trade"
    assert edge.timestamp > 0


def test_trust_edge_invalid_score():
    with pytest.raises(ValueError):
        TrustEdge("did:a", "did:b", 1.5)
    with pytest.raises(ValueError):
        TrustEdge("did:a", "did:b", -1.5)


def test_trust_edge_serialization():
    edge = TrustEdge("did:a", "did:b", 0.75)
    d = edge.to_dict()
    assert d["truster_did"] == "did:a"
    assert d["score"] == 0.75
    assert d["trust_level"] == "high"

    restored = TrustEdge.from_dict(d)
    assert restored.truster_did == edge.truster_did
    assert restored.score == edge.score


def test_trust_graph_add_node():
    tg = TrustGraph()
    tg.add_node("did:alice")
    assert tg.get_node_count() == 1
    tg.add_node("did:bob")
    assert tg.get_node_count() == 2


def test_trust_graph_set_and_get_trust():
    tg = TrustGraph()
    edge = tg.set_trust("did:alice", "did:bob", 0.9)
    assert edge.score == 0.9
    assert tg.get_node_count() == 2

    retrieved = tg.get_trust("did:alice", "did:bob")
    assert retrieved is not None
    assert retrieved.score == 0.9


def test_trust_graph_direct_trust_score():
    tg = TrustGraph()
    tg.set_trust("did:alice", "did:bob", 0.7)
    assert tg.get_direct_trust_score("did:alice", "did:bob") == 0.7
    assert tg.get_direct_trust_score("did:bob", "did:alice") == 0.0


def test_trust_graph_trustees_and_trusters():
    tg = TrustGraph()
    tg.set_trust("did:alice", "did:bob", 0.8)
    tg.set_trust("did:alice", "did:carol", 0.6)
    tg.set_trust("did:bob", "did:carol", 0.9)

    trustees = tg.get_trustees("did:alice")
    assert len(trustees) == 2

    trusters = tg.get_trusters("did:carol")
    assert len(trusters) == 2


def test_trust_propagation_direct():
    tg = TrustGraph()
    tg.set_trust("did:alice", "did:bob", 0.8)
    # Direct trust should be returned as-is
    score = tg.propagated_trust("did:alice", "did:bob")
    assert score == 0.8


def test_trust_propagation_transitive():
    tg = TrustGraph()
    tg.set_trust("did:alice", "did:bob", 0.8)
    tg.set_trust("did:bob", "did:carol", 0.9)
    # Transitive: alice -> bob -> carol
    score = tg.propagated_trust("did:alice", "did:carol")
    # Decay applied at each hop: 1.0 * 0.8 * 0.5 * 0.9 * 0.5 = 0.18
    assert 0.1 < score < 0.25


def test_trust_propagation_no_path():
    tg = TrustGraph()
    tg.add_node("did:alice")
    tg.add_node("did:bob")
    score = tg.propagated_trust("did:alice", "did:bob")
    assert score == 0.0


def test_reputation_computation():
    tg = TrustGraph()
    tg.set_trust("did:alice", "did:bob", 0.9)
    tg.set_trust("did:bob", "did:carol", 0.8)
    tg.set_trust("did:carol", "did:alice", 0.7)

    rep = tg.compute_reputation()
    assert len(rep) == 3
    # All nodes should have positive reputation
    for did, score in rep.items():
        assert 0.0 <= score <= 1.0
    # The most trusted node should have the highest reputation
    assert max(rep.values()) == 1.0


def test_reputation_empty_graph():
    tg = TrustGraph()
    rep = tg.compute_reputation()
    assert rep == {}


def test_trust_graph_serialization():
    tg = TrustGraph()
    tg.set_trust("did:a", "did:b", 0.5)
    tg.set_trust("did:b", "did:c", 0.7)
    d = tg.to_dict()
    assert d["node_count"] == 3
    assert d["edge_count"] == 2
    assert len(d["edges"]) == 2
    assert len(d["nodes"]) == 3
