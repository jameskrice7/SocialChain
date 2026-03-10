"""Governance API routes for communities, proposals, voting, trust, and sybil resistance.

Provides REST endpoints for:
- Community creation and management
- Proposal submission and voting
- Trust relationship management
- Sybil resistance vouching
- Reputation computation
"""
from flask import Blueprint, jsonify, request, current_app

from ...governance.community import Community, CommunityRole
from ...governance.proposal import ProposalStatus
from ...governance.voting import VotingMethod, VoteChoice
from ...social.trust import TrustLevel, score_to_trust_level
from ...blockchain.transaction import Transaction

governance_bp = Blueprint("governance", __name__)


# ── Community endpoints ──────────────────────────────────────────────────────

@governance_bp.route("/api/governance/communities", methods=["GET"])
def list_communities():
    state = current_app.app_state
    communities = [c.to_dict() for c in state.communities.values()]
    return jsonify({"communities": communities, "count": len(communities)}), 200


@governance_bp.route("/api/governance/communities", methods=["POST"])
def create_community():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["name", "founder_did"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {required}"}), 400

    founder_did = data["founder_did"]
    if not isinstance(founder_did, str) or not founder_did.startswith("did:"):
        return jsonify({"error": "Invalid founder DID format"}), 400

    voting_method = data.get("voting_method", "simple_majority")
    try:
        VotingMethod(voting_method)
    except ValueError:
        return jsonify({"error": f"Invalid voting method: {voting_method}"}), 400

    community = Community(
        name=data["name"],
        founder_did=founder_did,
        description=data.get("description", ""),
        voting_method=VotingMethod(voting_method),
        quorum_fraction=data.get("quorum_fraction", 0.5),
        pass_threshold=data.get("pass_threshold", 0.5),
    )
    state.communities[community.community_id] = community

    # Record community creation on blockchain
    tx = Transaction(
        sender=founder_did,
        recipient="NETWORK",
        data={
            "type": "community_create",
            "community_id": community.community_id,
            "name": community.name,
        },
    )
    state.blockchain.add_transaction(tx)

    return jsonify({
        "message": "Community created",
        "community": community.to_dict(),
        "tx_id": tx.tx_id,
    }), 201


@governance_bp.route("/api/governance/communities/<community_id>", methods=["GET"])
def get_community(community_id):
    state = current_app.app_state
    community = state.communities.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404
    return jsonify({"community": community.to_dict()}), 200


@governance_bp.route("/api/governance/communities/<community_id>/members", methods=["GET"])
def list_members(community_id):
    state = current_app.app_state
    community = state.communities.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404
    members = [m.to_dict() for m in community.list_members()]
    return jsonify({"members": members, "count": len(members)}), 200


@governance_bp.route("/api/governance/communities/<community_id>/members", methods=["POST"])
def add_member(community_id):
    state = current_app.app_state
    community = state.communities.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404

    data = request.get_json()
    if not data or "did" not in data:
        return jsonify({"error": "Missing 'did' field"}), 400

    did = data["did"]
    if not isinstance(did, str) or not did.startswith("did:"):
        return jsonify({"error": "Invalid DID format"}), 400

    try:
        membership = community.add_member(did, CommunityRole(data.get("role", "member")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "Member added", "membership": membership.to_dict()}), 201


# ── Proposal endpoints ───────────────────────────────────────────────────────

@governance_bp.route("/api/governance/communities/<community_id>/proposals", methods=["GET"])
def list_proposals(community_id):
    state = current_app.app_state
    community = state.communities.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404

    status_filter = request.args.get("status")
    proposals = [p.to_dict() for p in community.list_proposals(status=status_filter)]
    return jsonify({"proposals": proposals, "count": len(proposals)}), 200


@governance_bp.route("/api/governance/communities/<community_id>/proposals", methods=["POST"])
def create_proposal(community_id):
    state = current_app.app_state
    community = state.communities.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["proposer_did", "title"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {required}"}), 400

    try:
        proposal = community.create_proposal(
            proposer_did=data["proposer_did"],
            title=data["title"],
            description=data.get("description", ""),
            proposal_type=data.get("proposal_type", "custom"),
            parameters=data.get("parameters"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "Proposal created", "proposal": proposal.to_dict()}), 201


@governance_bp.route("/api/governance/proposals/<proposal_id>/activate", methods=["PATCH"])
def activate_proposal(proposal_id):
    state = current_app.app_state
    data = request.get_json() or {}
    activator_did = data.get("activator_did")
    if not activator_did:
        return jsonify({"error": "Missing activator_did"}), 400

    for community in state.communities.values():
        proposal = community.get_proposal(proposal_id)
        if proposal:
            try:
                community.activate_proposal(proposal_id, activator_did)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            return jsonify({"message": "Proposal activated", "proposal": proposal.to_dict()}), 200

    return jsonify({"error": "Proposal not found"}), 404


@governance_bp.route("/api/governance/proposals/<proposal_id>/vote", methods=["POST"])
def vote_on_proposal(proposal_id):
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["voter_did", "choice"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {required}"}), 400

    try:
        VoteChoice(data["choice"])
    except ValueError:
        return jsonify({"error": f"Invalid vote choice: {data['choice']}"}), 400

    for community in state.communities.values():
        proposal = community.get_proposal(proposal_id)
        if proposal:
            try:
                vote = community.vote_on_proposal(
                    proposal_id=proposal_id,
                    voter_did=data["voter_did"],
                    choice=data["choice"],
                    weight=data.get("weight", 1.0),
                )
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

            # Record vote on blockchain
            tx = Transaction(
                sender=data["voter_did"],
                recipient="NETWORK",
                data={
                    "type": "governance_vote",
                    "proposal_id": proposal_id,
                    "community_id": community.community_id,
                    "choice": data["choice"],
                },
            )
            state.blockchain.add_transaction(tx)

            return jsonify({
                "message": "Vote recorded",
                "vote": vote,
                "tx_id": tx.tx_id,
            }), 200

    return jsonify({"error": "Proposal not found"}), 404


@governance_bp.route("/api/governance/proposals/<proposal_id>/resolve", methods=["PATCH"])
def resolve_proposal(proposal_id):
    state = current_app.app_state
    for community in state.communities.values():
        proposal = community.get_proposal(proposal_id)
        if proposal:
            try:
                result = community.resolve_proposal(proposal_id)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

            # Record resolution on blockchain
            tx = Transaction(
                sender=community.founder_did,
                recipient="NETWORK",
                data={
                    "type": "proposal_resolved",
                    "proposal_id": proposal_id,
                    "community_id": community.community_id,
                    "passed": result["tally"]["passed"],
                },
            )
            state.blockchain.add_transaction(tx)

            return jsonify({
                "message": "Proposal resolved",
                "result": result,
                "tx_id": tx.tx_id,
            }), 200

    return jsonify({"error": "Proposal not found"}), 404


# ── Trust endpoints ──────────────────────────────────────────────────────────

@governance_bp.route("/api/governance/trust", methods=["POST"])
def set_trust():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["truster_did", "trustee_did", "score"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {required}"}), 400

    score = data["score"]
    if not isinstance(score, (int, float)) or not -1.0 <= score <= 1.0:
        return jsonify({"error": "Score must be a number between -1.0 and 1.0"}), 400

    edge = state.trust_graph.set_trust(
        truster_did=data["truster_did"],
        trustee_did=data["trustee_did"],
        score=score,
        context=data.get("context", "general"),
    )
    return jsonify({"message": "Trust set", "trust": edge.to_dict()}), 200


@governance_bp.route("/api/governance/trust/<did>", methods=["GET"])
def get_trust_info(did):
    state = current_app.app_state
    trustees = [e.to_dict() for e in state.trust_graph.get_trustees(did)]
    trusters = [e.to_dict() for e in state.trust_graph.get_trusters(did)]
    return jsonify({
        "did": did,
        "trustees": trustees,
        "trusters": trusters,
    }), 200


@governance_bp.route("/api/governance/trust/propagated", methods=["GET"])
def get_propagated_trust():
    state = current_app.app_state
    source = request.args.get("source")
    target = request.args.get("target")
    if not source or not target:
        return jsonify({"error": "Missing source and/or target query parameters"}), 400

    score = state.trust_graph.propagated_trust(source, target)
    return jsonify({
        "source": source,
        "target": target,
        "propagated_trust": score,
        "trust_level": score_to_trust_level(score).value,
    }), 200


@governance_bp.route("/api/governance/reputation", methods=["GET"])
def get_reputation():
    state = current_app.app_state
    reputation = state.trust_graph.compute_reputation()
    return jsonify({"reputation": reputation}), 200


# ── Sybil resistance endpoints ──────────────────────────────────────────────

@governance_bp.route("/api/governance/vouch", methods=["POST"])
def create_vouch():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["voucher_did", "vouchee_did"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {required}"}), 400

    try:
        vouch = state.sybil_resistance.create_vouch(
            voucher_did=data["voucher_did"],
            vouchee_did=data["vouchee_did"],
            message=data.get("message", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "Vouch created", "vouch": vouch.to_dict()}), 201


@governance_bp.route("/api/governance/vouch/<vouch_id>/accept", methods=["PATCH"])
def accept_vouch(vouch_id):
    state = current_app.app_state
    try:
        vouch = state.sybil_resistance.accept_vouch(vouch_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Record vouch acceptance on blockchain
    tx = Transaction(
        sender=vouch.voucher_did,
        recipient=vouch.vouchee_did,
        data={
            "type": "vouch_accepted",
            "vouch_id": vouch.vouch_id,
        },
    )
    state.blockchain.add_transaction(tx)

    return jsonify({
        "message": "Vouch accepted",
        "vouch": vouch.to_dict(),
        "tx_id": tx.tx_id,
    }), 200


@governance_bp.route("/api/governance/vouch/<vouch_id>/revoke", methods=["PATCH"])
def revoke_vouch(vouch_id):
    state = current_app.app_state
    try:
        vouch = state.sybil_resistance.revoke_vouch(vouch_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "Vouch revoked", "vouch": vouch.to_dict()}), 200


@governance_bp.route("/api/governance/verification/<did>", methods=["GET"])
def get_verification(did):
    state = current_app.app_state
    level = state.sybil_resistance.compute_verification_level(did)
    vouches = [v.to_dict() for v in state.sybil_resistance.get_vouches_for(did)]
    return jsonify({
        "did": did,
        "verification_level": level.value,
        "vouches": vouches,
    }), 200


@governance_bp.route("/api/governance/sybil-analysis/<did>", methods=["GET"])
def sybil_analysis(did):
    state = current_app.app_state
    analysis = state.sybil_resistance.detect_sybil_cluster(did)
    return jsonify({"analysis": analysis}), 200
