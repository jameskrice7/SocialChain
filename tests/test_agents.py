import pytest
from socialchain.agents import AIAgent, AgentTask, TaskStatus
from socialchain.blockchain import Blockchain


def test_agent_creation():
    agent = AIAgent(name="TestAgent", capabilities=["echo"])
    assert agent.name == "TestAgent"
    assert "echo" in agent.capabilities
    assert agent.did.startswith("did:socialchain:")


def test_agent_task_creation():
    task = AgentTask(description="Test task", payload={"key": "value"})
    assert task.description == "Test task"
    assert task.status == TaskStatus.QUEUED
    assert task.task_id is not None


def test_agent_submit_task():
    agent = AIAgent(name="TestAgent", capabilities=["echo"])
    task = AgentTask(description="Echo test", payload={"capability": "echo", "msg": "hello"})
    task_id = agent.submit_task(task)
    assert task_id == task.task_id
    assert len(agent.task_queue) == 1


def test_agent_execute_task():
    agent = AIAgent(name="TestAgent", capabilities=["echo"])
    task = AgentTask(description="Echo test", payload={"capability": "echo", "msg": "hello"})
    agent.submit_task(task)
    completed_task = agent.run_next_task()
    assert completed_task is not None
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.result is not None


def test_agent_register_on_blockchain():
    agent = AIAgent(name="BlockchainAgent", capabilities=["echo"])
    bc = Blockchain()
    tx = agent.register_on_blockchain(bc)
    assert tx.sender == agent.did
    assert tx.recipient == "NETWORK"
    assert tx.data["type"] == "agent_registration"
    assert len(bc.pending_transactions) == 1


def test_agent_task_to_dict():
    task = AgentTask(description="Test", payload={"x": 1})
    d = task.to_dict()
    assert d["description"] == "Test"
    assert d["status"] == "QUEUED"
    assert d["payload"] == {"x": 1}


def test_agent_to_dict():
    agent = AIAgent(name="Agent1", capabilities=["echo", "store"])
    d = agent.to_dict()
    assert d["name"] == "Agent1"
    assert "echo" in d["capabilities"]
    assert d["did"].startswith("did:socialchain:")
