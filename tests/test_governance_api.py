"""Tests for Governance API routes."""
import pytest


def _register_user(client, username="govuser"):
    """Helper to register a user and return their DID."""
    # Clear any existing session so register doesn't redirect
    client.get("/logout")
    client.post("/register", data={
        "username": username,
        "password": "pw",
        "confirm_password": "pw",
        "agent_type": "human",
    })
    with client.session_transaction() as sess:
        return sess.get("user_did")


def test_create_community(client):
    user_did = _register_user(client)
    resp = client.post("/api/governance/communities", json={
        "name": "Test Community",
        "founder_did": user_did,
        "description": "A governance test community",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["community"]["name"] == "Test Community"
    assert data["community"]["member_count"] == 1
    assert "tx_id" in data


def test_create_community_missing_fields(client):
    resp = client.post("/api/governance/communities", json={"name": "No founder"})
    assert resp.status_code == 400


def test_create_community_invalid_did(client):
    resp = client.post("/api/governance/communities", json={
        "name": "Bad DID",
        "founder_did": "not-a-did",
    })
    assert resp.status_code == 400


def test_list_communities(client):
    user_did = _register_user(client)
    client.post("/api/governance/communities", json={
        "name": "List Test",
        "founder_did": user_did,
    })
    resp = client.get("/api/governance/communities")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 1


def test_get_community(client):
    user_did = _register_user(client)
    create_resp = client.post("/api/governance/communities", json={
        "name": "Get Test",
        "founder_did": user_did,
    })
    cid = create_resp.get_json()["community"]["community_id"]
    resp = client.get(f"/api/governance/communities/{cid}")
    assert resp.status_code == 200
    assert resp.get_json()["community"]["name"] == "Get Test"


def test_get_community_not_found(client):
    resp = client.get("/api/governance/communities/nonexistent")
    assert resp.status_code == 404


def test_add_member(client):
    user_did = _register_user(client, "founder1")
    create_resp = client.post("/api/governance/communities", json={
        "name": "Member Test",
        "founder_did": user_did,
    })
    cid = create_resp.get_json()["community"]["community_id"]

    member_did = _register_user(client, "member1")
    resp = client.post(f"/api/governance/communities/{cid}/members", json={
        "did": member_did,
    })
    assert resp.status_code == 201
    assert resp.get_json()["membership"]["role"] == "member"


def test_list_members(client):
    user_did = _register_user(client, "listfounder")
    create_resp = client.post("/api/governance/communities", json={
        "name": "List Members",
        "founder_did": user_did,
    })
    cid = create_resp.get_json()["community"]["community_id"]
    resp = client.get(f"/api/governance/communities/{cid}/members")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 1  # Just the founder


def test_proposal_workflow(client):
    """Full proposal lifecycle through API."""
    founder_did = _register_user(client, "propfounder")
    create_resp = client.post("/api/governance/communities", json={
        "name": "Proposal Test",
        "founder_did": founder_did,
    })
    cid = create_resp.get_json()["community"]["community_id"]

    # Add more members
    member1_did = _register_user(client, "propmember1")
    member2_did = _register_user(client, "propmember2")
    client.post(f"/api/governance/communities/{cid}/members", json={"did": member1_did})
    client.post(f"/api/governance/communities/{cid}/members", json={"did": member2_did})

    # Create proposal
    prop_resp = client.post(f"/api/governance/communities/{cid}/proposals", json={
        "proposer_did": founder_did,
        "title": "New Policy",
        "description": "Let's change something",
        "proposal_type": "policy_change",
    })
    assert prop_resp.status_code == 201
    pid = prop_resp.get_json()["proposal"]["proposal_id"]

    # Activate proposal
    activate_resp = client.patch(f"/api/governance/proposals/{pid}/activate", json={
        "activator_did": founder_did,
    })
    assert activate_resp.status_code == 200
    assert activate_resp.get_json()["proposal"]["status"] == "active"

    # Vote
    vote_resp = client.post(f"/api/governance/proposals/{pid}/vote", json={
        "voter_did": founder_did,
        "choice": "for",
    })
    assert vote_resp.status_code == 200

    vote_resp2 = client.post(f"/api/governance/proposals/{pid}/vote", json={
        "voter_did": member1_did,
        "choice": "for",
    })
    assert vote_resp2.status_code == 200

    vote_resp3 = client.post(f"/api/governance/proposals/{pid}/vote", json={
        "voter_did": member2_did,
        "choice": "against",
    })
    assert vote_resp3.status_code == 200

    # Resolve
    resolve_resp = client.patch(f"/api/governance/proposals/{pid}/resolve")
    assert resolve_resp.status_code == 200
    result = resolve_resp.get_json()["result"]
    assert result["tally"]["passed"] is True
    assert result["proposal"]["status"] == "passed"


def test_list_proposals(client):
    founder_did = _register_user(client, "listpropfounder")
    create_resp = client.post("/api/governance/communities", json={
        "name": "List Proposals",
        "founder_did": founder_did,
    })
    cid = create_resp.get_json()["community"]["community_id"]
    client.post(f"/api/governance/communities/{cid}/proposals", json={
        "proposer_did": founder_did,
        "title": "Proposal A",
    })
    resp = client.get(f"/api/governance/communities/{cid}/proposals")
    assert resp.status_code == 200
    assert resp.get_json()["count"] >= 1


def test_vote_invalid_choice(client):
    founder_did = _register_user(client, "invalidvoter")
    create_resp = client.post("/api/governance/communities", json={
        "name": "Invalid Vote",
        "founder_did": founder_did,
    })
    cid = create_resp.get_json()["community"]["community_id"]
    prop_resp = client.post(f"/api/governance/communities/{cid}/proposals", json={
        "proposer_did": founder_did,
        "title": "Test",
    })
    pid = prop_resp.get_json()["proposal"]["proposal_id"]
    client.patch(f"/api/governance/proposals/{pid}/activate", json={
        "activator_did": founder_did,
    })
    resp = client.post(f"/api/governance/proposals/{pid}/vote", json={
        "voter_did": founder_did,
        "choice": "invalid",
    })
    assert resp.status_code == 400


# ── Trust API Tests ──────────────────────────────────────────────────────────

def test_set_trust(client):
    resp = client.post("/api/governance/trust", json={
        "truster_did": "did:socialchain:alice",
        "trustee_did": "did:socialchain:bob",
        "score": 0.8,
        "context": "trade",
    })
    assert resp.status_code == 200
    assert resp.get_json()["trust"]["score"] == 0.8


def test_set_trust_invalid_score(client):
    resp = client.post("/api/governance/trust", json={
        "truster_did": "did:a",
        "trustee_did": "did:b",
        "score": 5.0,
    })
    assert resp.status_code == 400


def test_get_trust_info(client):
    client.post("/api/governance/trust", json={
        "truster_did": "did:socialchain:alice",
        "trustee_did": "did:socialchain:bob",
        "score": 0.7,
    })
    resp = client.get("/api/governance/trust/did:socialchain:alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["trustees"]) >= 1


def test_propagated_trust(client):
    client.post("/api/governance/trust", json={
        "truster_did": "did:a", "trustee_did": "did:b", "score": 0.9,
    })
    client.post("/api/governance/trust", json={
        "truster_did": "did:b", "trustee_did": "did:c", "score": 0.8,
    })
    resp = client.get("/api/governance/trust/propagated?source=did:a&target=did:c")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["propagated_trust"] > 0


def test_propagated_trust_missing_params(client):
    resp = client.get("/api/governance/trust/propagated")
    assert resp.status_code == 400


def test_reputation(client):
    client.post("/api/governance/trust", json={
        "truster_did": "did:x", "trustee_did": "did:y", "score": 0.9,
    })
    resp = client.get("/api/governance/reputation")
    assert resp.status_code == 200
    assert "reputation" in resp.get_json()


# ── Vouch / Sybil API Tests ─────────────────────────────────────────────────

def test_create_vouch(client):
    resp = client.post("/api/governance/vouch", json={
        "voucher_did": "did:socialchain:alice",
        "vouchee_did": "did:socialchain:bob",
        "message": "I know Bob personally",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["vouch"]["status"] == "pending"


def test_accept_vouch(client):
    create_resp = client.post("/api/governance/vouch", json={
        "voucher_did": "did:socialchain:alice2",
        "vouchee_did": "did:socialchain:bob2",
    })
    vouch_id = create_resp.get_json()["vouch"]["vouch_id"]
    resp = client.patch(f"/api/governance/vouch/{vouch_id}/accept")
    assert resp.status_code == 200
    assert resp.get_json()["vouch"]["status"] == "accepted"
    assert "tx_id" in resp.get_json()


def test_revoke_vouch(client):
    create_resp = client.post("/api/governance/vouch", json={
        "voucher_did": "did:socialchain:revoker",
        "vouchee_did": "did:socialchain:revokee",
    })
    vouch_id = create_resp.get_json()["vouch"]["vouch_id"]
    client.patch(f"/api/governance/vouch/{vouch_id}/accept")
    resp = client.patch(f"/api/governance/vouch/{vouch_id}/revoke")
    assert resp.status_code == 200
    assert resp.get_json()["vouch"]["status"] == "revoked"


def test_verification_level(client):
    resp = client.get("/api/governance/verification/did:socialchain:someone")
    assert resp.status_code == 200
    assert resp.get_json()["verification_level"] == "unverified"


def test_sybil_analysis(client):
    resp = client.get("/api/governance/sybil-analysis/did:socialchain:suspect")
    assert resp.status_code == 200
    assert "analysis" in resp.get_json()
