"""Sybil Resistance through social vouching and graph analysis.

Inspired by Ehud Shapiro's work on Sybil-resilient social choice, this module
implements identity verification through a web-of-trust vouching system. The
core insight is that creating fake identities is easy, but building genuine
social connections is hard - attackers can create many nodes but cannot easily
get legitimate users to vouch for them.
"""
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from .trust import TrustGraph, TrustLevel, score_to_trust_level


class VouchStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class VerificationLevel(str, Enum):
    """Identity verification tiers based on vouching depth."""
    UNVERIFIED = "unverified"
    BASIC = "basic"         # At least 1 vouch
    STANDARD = "standard"   # At least 3 vouches from verified users
    TRUSTED = "trusted"     # At least 5 vouches, including 2+ from STANDARD+


# Requirements for each verification level
VERIFICATION_REQUIREMENTS = {
    VerificationLevel.BASIC: {"min_vouches": 1, "min_verified_vouches": 0},
    VerificationLevel.STANDARD: {"min_vouches": 3, "min_verified_vouches": 2},
    VerificationLevel.TRUSTED: {"min_vouches": 5, "min_verified_vouches": 3},
}


class Vouch:
    """A vouching relationship where one identity vouches for another's legitimacy."""

    def __init__(self, voucher_did: str, vouchee_did: str,
                 vouch_id: Optional[str] = None,
                 status: VouchStatus = VouchStatus.PENDING,
                 message: str = "",
                 timestamp: Optional[float] = None):
        self.vouch_id = vouch_id or str(uuid.uuid4())
        self.voucher_did = voucher_did
        self.vouchee_did = vouchee_did
        self.status = status
        self.message = message
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "vouch_id": self.vouch_id,
            "voucher_did": self.voucher_did,
            "vouchee_did": self.vouchee_did,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Vouch":
        return cls(
            voucher_did=d["voucher_did"],
            vouchee_did=d["vouchee_did"],
            vouch_id=d.get("vouch_id"),
            status=VouchStatus(d.get("status", "pending")),
            message=d.get("message", ""),
            timestamp=d.get("timestamp"),
        )


class SybilResistance:
    """Manages identity verification through social vouching.

    Implements Shapiro's insight that Sybil attacks can be detected through
    graph structure analysis - legitimate social clusters have dense internal
    connections, while Sybil clusters connect to the honest region through
    a small number of attack edges.
    """

    def __init__(self, trust_graph: TrustGraph):
        self.trust_graph = trust_graph
        self._vouches: Dict[str, Vouch] = {}  # vouch_id -> Vouch
        self._identity_vouches: Dict[str, List[str]] = {}  # did -> [vouch_ids received]
        self._verification_cache: Dict[str, VerificationLevel] = {}

    def create_vouch(self, voucher_did: str, vouchee_did: str,
                     message: str = "") -> Vouch:
        """Create a vouch for another identity."""
        if voucher_did == vouchee_did:
            raise ValueError("Cannot vouch for yourself")

        # Check for duplicate vouches
        for vouch_id in self._identity_vouches.get(vouchee_did, []):
            vouch = self._vouches[vouch_id]
            if vouch.voucher_did == voucher_did and vouch.status != VouchStatus.REVOKED:
                raise ValueError("Already vouched for this identity")

        vouch = Vouch(voucher_did, vouchee_did, message=message)
        self._vouches[vouch.vouch_id] = vouch
        if vouchee_did not in self._identity_vouches:
            self._identity_vouches[vouchee_did] = []
        self._identity_vouches[vouchee_did].append(vouch.vouch_id)

        # Invalidate verification cache for vouchee
        self._verification_cache.pop(vouchee_did, None)

        return vouch

    def accept_vouch(self, vouch_id: str) -> Vouch:
        """Accept a pending vouch."""
        vouch = self._vouches.get(vouch_id)
        if not vouch:
            raise ValueError("Vouch not found")
        if vouch.status != VouchStatus.PENDING:
            raise ValueError("Vouch is not pending")
        vouch.status = VouchStatus.ACCEPTED

        # Update trust graph - vouching implies trust
        self.trust_graph.set_trust(
            vouch.voucher_did, vouch.vouchee_did, 0.8, context="vouch"
        )

        # Invalidate cache
        self._verification_cache.pop(vouch.vouchee_did, None)
        return vouch

    def revoke_vouch(self, vouch_id: str) -> Vouch:
        """Revoke a previously accepted vouch."""
        vouch = self._vouches.get(vouch_id)
        if not vouch:
            raise ValueError("Vouch not found")
        vouch.status = VouchStatus.REVOKED

        # Update trust graph
        self.trust_graph.set_trust(
            vouch.voucher_did, vouch.vouchee_did, -0.5, context="vouch_revoked"
        )

        # Invalidate cache
        self._verification_cache.pop(vouch.vouchee_did, None)
        return vouch

    def get_vouches_for(self, did: str) -> List[Vouch]:
        """Get all vouches received by an identity."""
        vouch_ids = self._identity_vouches.get(did, [])
        return [self._vouches[vid] for vid in vouch_ids if vid in self._vouches]

    def get_accepted_vouches_for(self, did: str) -> List[Vouch]:
        """Get only accepted vouches for an identity."""
        return [v for v in self.get_vouches_for(did) if v.status == VouchStatus.ACCEPTED]

    def compute_verification_level(self, did: str) -> VerificationLevel:
        """Compute the verification level for an identity based on its vouches."""
        if did in self._verification_cache:
            return self._verification_cache[did]

        accepted = self.get_accepted_vouches_for(did)
        total_vouches = len(accepted)

        # Count vouches from verified users (at least BASIC level)
        verified_vouches = 0
        for vouch in accepted:
            voucher_level = self._verification_cache.get(vouch.voucher_did,
                                                         VerificationLevel.UNVERIFIED)
            if voucher_level != VerificationLevel.UNVERIFIED:
                verified_vouches += 1

        level = VerificationLevel.UNVERIFIED
        for check_level in [VerificationLevel.TRUSTED, VerificationLevel.STANDARD,
                            VerificationLevel.BASIC]:
            reqs = VERIFICATION_REQUIREMENTS[check_level]
            if (total_vouches >= reqs["min_vouches"]
                    and verified_vouches >= reqs["min_verified_vouches"]):
                level = check_level
                break

        self._verification_cache[did] = level
        return level

    def detect_sybil_cluster(self, suspect_did: str, min_cluster_size: int = 3) -> Dict[str, Any]:
        """Analyze the trust graph around a suspect identity for Sybil patterns.

        Sybil clusters are characterized by:
        1. Dense internal connections within the cluster
        2. Few connections to the honest network region
        3. Low diversity of vouchers (all from same small group)

        Returns analysis results including risk score and cluster info.
        """
        # Get all trusters and trustees of the suspect
        trusters = self.trust_graph.get_trusters(suspect_did)
        trustees = self.trust_graph.get_trustees(suspect_did)

        truster_dids = {e.truster_did for e in trusters}
        trustee_dids = {e.trustee_did for e in trustees}
        neighborhood = truster_dids | trustee_dids

        if len(neighborhood) < min_cluster_size:
            return {
                "suspect_did": suspect_did,
                "risk_score": 0.0,
                "cluster_size": len(neighborhood),
                "analysis": "insufficient_data",
                "is_suspicious": False,
            }

        # Measure internal density of the neighborhood
        internal_edges = 0
        external_edges = 0
        for node_did in neighborhood:
            for edge in self.trust_graph.get_trustees(node_did):
                if edge.trustee_did in neighborhood:
                    internal_edges += 1
                else:
                    external_edges += 1

        total_possible_internal = len(neighborhood) * (len(neighborhood) - 1)
        internal_density = internal_edges / total_possible_internal if total_possible_internal > 0 else 0

        # High internal density + low external connections = suspicious
        total_edges = internal_edges + external_edges
        external_ratio = external_edges / total_edges if total_edges > 0 else 0

        # Risk score: high density + low external ratio = suspicious
        risk_score = max(0.0, min(1.0, internal_density * (1.0 - external_ratio)))

        return {
            "suspect_did": suspect_did,
            "risk_score": round(risk_score, 3),
            "cluster_size": len(neighborhood),
            "internal_density": round(internal_density, 3),
            "external_ratio": round(external_ratio, 3),
            "analysis": "sybil_risk" if risk_score > 0.7 else "normal",
            "is_suspicious": risk_score > 0.7,
        }

    def get_vouch(self, vouch_id: str) -> Optional[Vouch]:
        return self._vouches.get(vouch_id)

    def to_dict(self) -> dict:
        return {
            "total_vouches": len(self._vouches),
            "identities_tracked": len(self._identity_vouches),
            "vouches": [v.to_dict() for v in self._vouches.values()],
        }
