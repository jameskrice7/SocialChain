"""Tests for internet/search API endpoints and agent search capabilities."""
import pytest
from unittest.mock import patch, MagicMock

from socialchain.agents.agent import AIAgent, _web_search
from socialchain.agents.task import AgentTask, TaskStatus


def test_internet_topology_endpoint(client):
    resp = client.get("/api/internet/topology")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tiers" in data
    assert "links" in data
    assert len(data["tiers"]) >= 3
    # Verify SocialChain nodes are present
    tier_names = [t["name"] for t in data["tiers"]]
    assert "SocialChain Nodes" in tier_names


def test_search_endpoint_missing_query(client):
    resp = client.get("/api/search")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_search_endpoint_query_too_long(client):
    resp = client.get("/api/search?q=" + "a" * 300)
    assert resp.status_code == 400


def test_search_endpoint_with_mocked_ddg(client):
    """Test search endpoint with mocked DuckDuckGo response."""
    mock_response = {
        "AbstractText": "Blockchain is a distributed ledger technology.",
        "AbstractURL": "https://en.wikipedia.org/wiki/Blockchain",
        "Heading": "Blockchain",
        "AbstractSource": "Wikipedia",
        "RelatedTopics": [
            {
                "Text": "Bitcoin - The first cryptocurrency using blockchain.",
                "FirstURL": "https://en.wikipedia.org/wiki/Bitcoin",
            }
        ],
        "Answer": "",
    }

    with patch("socialchain.api.routes.internet._requests") as mock_req:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_req.get.return_value = mock_resp

        resp = client.get("/api/search?q=blockchain")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["query"] == "blockchain"
        assert len(data["results"]) >= 1
        assert data["results"][0]["type"] == "abstract"


def test_agent_search_handler_with_mock():
    """Test agent web search handler with mocked HTTP call."""
    agent = AIAgent(name="SearchBot", capabilities=["chat", "search"])

    mock_search_data = {
        "query": "blockchain",
        "results": [
            {
                "title": "Blockchain",
                "snippet": "A blockchain is a distributed ledger.",
                "url": "https://en.wikipedia.org/wiki/Blockchain",
            }
        ],
        "abstract": "A blockchain is a distributed ledger.",
    }

    with patch("socialchain.agents.agent._web_search", return_value=mock_search_data):
        task = AgentTask(
            description="search",
            payload={"capability": "search", "query": "blockchain"},
        )
        agent.submit_task(task)
        completed = agent.run_next_task()
        assert completed is not None
        assert completed.status == TaskStatus.COMPLETED
        assert "reply" in completed.result
        assert "blockchain" in completed.result["reply"].lower()
        assert completed.result["type"] == "search"


def test_agent_chat_search_prefix():
    """Test that 'search: X' prefix in chat triggers web search."""
    agent = AIAgent(name="ChainBot", capabilities=["chat"])

    mock_search_data = {
        "query": "smart contracts",
        "results": [],
        "abstract": "Smart contracts are self-executing programs.",
    }

    with patch("socialchain.agents.agent._web_search", return_value=mock_search_data):
        task = AgentTask(
            description="chat",
            payload={"capability": "chat", "message": "search: smart contracts"},
        )
        agent.submit_task(task)
        completed = agent.run_next_task()
        assert completed is not None
        assert completed.status == TaskStatus.COMPLETED
        assert completed.result.get("type") == "search"


def test_agent_chat_web_prefix():
    """Test that 'web: X' prefix triggers web search."""
    agent = AIAgent(name="ChainBot", capabilities=["chat"])

    mock_search_data = {
        "query": "decentralized internet",
        "results": [],
        "abstract": "Decentralization of the web.",
    }

    with patch("socialchain.agents.agent._web_search", return_value=mock_search_data):
        task = AgentTask(
            description="chat",
            payload={"capability": "chat", "message": "web: decentralized internet"},
        )
        agent.submit_task(task)
        completed = agent.run_next_task()
        assert completed.status == TaskStatus.COMPLETED
        assert completed.result.get("type") == "search"


def test_agent_status_endpoint(client):
    """Test agent status update on blockchain."""
    # Register an agent
    reg_resp = client.post("/api/agents", json={
        "name": "StatusAgent",
        "capabilities": ["chat"],
    })
    assert reg_resp.status_code == 201
    agent_did = reg_resp.get_json()["agent"]["did"]

    from urllib.parse import quote
    encoded = quote(agent_did, safe="")
    resp = client.post(f"/api/agents/{encoded}/status", json={"status": "active"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "active"
    assert "tx_id" in data


def test_agent_status_invalid(client):
    """Test that invalid status is rejected."""
    reg_resp = client.post("/api/agents", json={
        "name": "StatusAgent2",
        "capabilities": ["chat"],
    })
    agent_did = reg_resp.get_json()["agent"]["did"]

    from urllib.parse import quote
    encoded = quote(agent_did, safe="")
    resp = client.post(f"/api/agents/{encoded}/status", json={"status": "invalid_status"})
    assert resp.status_code == 400


def test_internet_page_requires_auth(client):
    """Test that the internet page requires authentication."""
    resp = client.get("/internet", follow_redirects=False)
    assert resp.status_code == 302


def test_contracts_page_requires_auth(client):
    """Test that the contracts page requires authentication."""
    resp = client.get("/contracts", follow_redirects=False)
    assert resp.status_code == 302
