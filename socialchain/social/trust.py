"""Trust and Reputation System inspired by Ehud Shapiro's work on digital social contracts.

Implements mathematical trust scoring, trust propagation through social graphs,
and reputation computation using eigenvector-like centrality measures. Trust
relationships are directional and weighted, allowing asymmetric trust between
participants in the network.
"""
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TrustLevel(str, Enum):
    """Discrete trust levels for coarse-grained trust assessment."""
    UNKNOWN = "unknown"
    DISTRUSTED = "distrusted"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VOUCHED = "vouched"


# Mapping from trust level to numerical score boundaries
TRUST_LEVEL_THRESHOLDS = {
    TrustLevel.DISTRUSTED: (-1.0, -0.2),
    TrustLevel.UNKNOWN: (-0.2, 0.2),
    TrustLevel.LOW: (0.2, 0.4),
    TrustLevel.MEDIUM: (0.4, 0.7),
    TrustLevel.HIGH: (0.7, 0.9),
    TrustLevel.VOUCHED: (0.9, 1.0),
}


def score_to_trust_level(score: float) -> TrustLevel:
    """Convert a numerical trust score to a discrete trust level."""
    if score <= -0.2:
        return TrustLevel.DISTRUSTED
    elif score < 0.2:
        return TrustLevel.UNKNOWN
    elif score < 0.4:
        return TrustLevel.LOW
    elif score < 0.7:
        return TrustLevel.MEDIUM
    elif score < 0.9:
        return TrustLevel.HIGH
    else:
        return TrustLevel.VOUCHED


class TrustEdge:
    """A directed, weighted trust relationship between two identities."""

    def __init__(self, truster_did: str, trustee_did: str, score: float,
                 context: str = "general", timestamp: Optional[float] = None):
        if not -1.0 <= score <= 1.0:
            raise ValueError("Trust score must be between -1.0 and 1.0")
        self.truster_did = truster_did
        self.trustee_did = trustee_did
        self.score = score
        self.context = context
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "truster_did": self.truster_did,
            "trustee_did": self.trustee_did,
            "score": self.score,
            "context": self.context,
            "timestamp": self.timestamp,
            "trust_level": score_to_trust_level(self.score).value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrustEdge":
        return cls(
            truster_did=d["truster_did"],
            trustee_did=d["trustee_did"],
            score=d["score"],
            context=d.get("context", "general"),
            timestamp=d.get("timestamp"),
        )


class TrustGraph:
    """Directed weighted trust graph for computing reputation and trust propagation.

    Inspired by Shapiro's work on mathematical social infrastructure, this graph
    supports:
    - Direct trust assignment between identities
    - Trust propagation through transitive paths with decay
    - Reputation scoring via iterative convergence (PageRank-like)
    - Trust context (e.g., 'governance', 'trade', 'general')
    """

    PROPAGATION_DECAY = 0.5  # Trust decays by half per hop
    MAX_PROPAGATION_DEPTH = 3  # Maximum hops for trust propagation
    REPUTATION_DAMPING = 0.85  # PageRank-style damping factor
    REPUTATION_ITERATIONS = 20  # Convergence iterations

    def __init__(self):
        # truster_did -> {trustee_did -> TrustEdge}
        self._edges: Dict[str, Dict[str, TrustEdge]] = {}
        self._nodes: set = set()

    def add_node(self, did: str) -> None:
        """Register an identity in the trust graph."""
        self._nodes.add(did)
        if did not in self._edges:
            self._edges[did] = {}

    def set_trust(self, truster_did: str, trustee_did: str, score: float,
                  context: str = "general") -> TrustEdge:
        """Set or update a direct trust relationship."""
        self.add_node(truster_did)
        self.add_node(trustee_did)
        edge = TrustEdge(truster_did, trustee_did, score, context)
        self._edges[truster_did][trustee_did] = edge
        return edge

    def get_trust(self, truster_did: str, trustee_did: str) -> Optional[TrustEdge]:
        """Get the direct trust edge between two identities."""
        return self._edges.get(truster_did, {}).get(trustee_did)

    def get_direct_trust_score(self, truster_did: str, trustee_did: str) -> float:
        """Get the direct trust score, or 0.0 if no relationship exists."""
        edge = self.get_trust(truster_did, trustee_did)
        return edge.score if edge else 0.0

    def get_trustees(self, did: str) -> List[TrustEdge]:
        """Get all identities that a given identity trusts."""
        return list(self._edges.get(did, {}).values())

    def get_trusters(self, did: str) -> List[TrustEdge]:
        """Get all identities that trust a given identity."""
        trusters = []
        for truster_did, edges in self._edges.items():
            if did in edges:
                trusters.append(edges[did])
        return trusters

    def propagated_trust(self, source_did: str, target_did: str,
                         max_depth: Optional[int] = None) -> float:
        """Compute trust from source to target via transitive trust propagation.

        Uses BFS with exponential decay: trust at depth d is multiplied by
        PROPAGATION_DECAY^d. This implements Shapiro's principle that trust
        weakens with social distance.
        """
        if max_depth is None:
            max_depth = self.MAX_PROPAGATION_DEPTH

        # Direct trust takes priority
        direct = self.get_direct_trust_score(source_did, target_did)
        if direct != 0.0:
            return direct

        # BFS propagation
        visited = {source_did}
        # Queue: (current_did, accumulated_trust, depth)
        queue: List[Tuple[str, float, int]] = [(source_did, 1.0, 0)]
        max_trust = 0.0

        while queue:
            current, accumulated, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for edge in self.get_trustees(current):
                if edge.trustee_did == target_did:
                    path_trust = accumulated * edge.score * self.PROPAGATION_DECAY
                    if abs(path_trust) > abs(max_trust):
                        max_trust = path_trust
                elif edge.trustee_did not in visited and edge.score > 0:
                    visited.add(edge.trustee_did)
                    next_trust = accumulated * edge.score * self.PROPAGATION_DECAY
                    queue.append((edge.trustee_did, next_trust, depth + 1))

        return max(min(max_trust, 1.0), -1.0)

    def compute_reputation(self) -> Dict[str, float]:
        """Compute global reputation scores using iterative convergence.

        Similar to PageRank, each node's reputation is determined by the
        trust-weighted sum of its trusters' reputations. Implements Shapiro's
        vision of mathematically-grounded social standing.
        """
        nodes = list(self._nodes)
        if not nodes:
            return {}

        n = len(nodes)
        # Initialize all reputations equally
        reputation: Dict[str, float] = {did: 1.0 / n for did in nodes}

        for _ in range(self.REPUTATION_ITERATIONS):
            new_rep: Dict[str, float] = {}
            for did in nodes:
                # Sum of trust-weighted reputations from trusters
                incoming_trust = 0.0
                trusters = self.get_trusters(did)
                for edge in trusters:
                    if edge.score > 0:
                        incoming_trust += edge.score * reputation[edge.truster_did]

                new_rep[did] = (
                    (1 - self.REPUTATION_DAMPING) / n
                    + self.REPUTATION_DAMPING * incoming_trust
                )
            reputation = new_rep

        # Normalize to [0, 1]
        max_rep = max(reputation.values()) if reputation else 1.0
        if max_rep > 0:
            reputation = {did: r / max_rep for did, r in reputation.items()}

        return reputation

    def get_node_count(self) -> int:
        return len(self._nodes)

    def get_edge_count(self) -> int:
        return sum(len(edges) for edges in self._edges.values())

    def to_dict(self) -> dict:
        """Serialize the trust graph for API responses."""
        edges = []
        for truster_edges in self._edges.values():
            for edge in truster_edges.values():
                edges.append(edge.to_dict())
        return {
            "nodes": list(self._nodes),
            "edges": edges,
            "node_count": self.get_node_count(),
            "edge_count": self.get_edge_count(),
        }
