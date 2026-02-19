import time
from flask import Blueprint, jsonify, request, current_app
from ...agents.agent import AIAgent
from ...agents.task import AgentTask

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("/api/agents", methods=["GET"])
def list_agents():
    state = current_app.app_state
    agents = [a.to_dict() for a in state.agent_registry.values()]
    return jsonify({"agents": agents}), 200


@agents_bp.route("/api/agents", methods=["POST"])
def register_agent():
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    name = data.get("name")
    if not name:
        return jsonify({"error": "Missing name"}), 400
    capabilities = data.get("capabilities", [])
    agent = AIAgent(name=name, capabilities=capabilities)
    agent.register_on_blockchain(state.blockchain)
    state.agent_registry[agent.did] = agent
    return jsonify({"message": "Agent registered", "agent": agent.to_dict()}), 201


@agents_bp.route("/api/agents/chat", methods=["POST"])
def agent_chat():
    """Chat with any available agent (or the first one if none specified)."""
    state = current_app.app_state
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Missing message"}), 400

    agent_did = data.get("agent_did")
    if agent_did and agent_did in state.agent_registry:
        agent = state.agent_registry[agent_did]
    elif state.agent_registry:
        agent = next(iter(state.agent_registry.values()))
    else:
        # Bootstrap a default assistant agent on first chat
        agent = AIAgent(
            name="ChainBot",
            capabilities=["chat", "echo", "autonomous_post"],
        )
        agent.register_on_blockchain(state.blockchain)
        state.agent_registry[agent.did] = agent

    task = AgentTask(
        description="chat",
        payload={"capability": "chat", "message": message},
    )
    agent.submit_task(task)
    completed = agent.run_next_task()
    result = completed.result if completed else {"reply": "No response.", "agent": agent.name, "agent_did": agent.did}
    return jsonify(result), 200


@agents_bp.route("/api/agents/feed", methods=["GET"])
def agent_feed():
    """Return recent autonomous-post activity from all registered agents."""
    state = current_app.app_state
    topics = ["network", "blockchain", "contract", "audit"]
    feed = []
    for agent in list(state.agent_registry.values()):
        for topic in topics:
            task = AgentTask(
                description="autonomous_post",
                payload={"capability": "autonomous_post", "topic": topic},
            )
            agent.submit_task(task)
            done = agent.run_next_task()
            if done and done.result and "post" in done.result:
                feed.append({
                    "agent": agent.name,
                    "agent_did": agent.did,
                    "topic": topic,
                    "post": done.result["post"],
                    "timestamp": time.time(),
                })
    return jsonify({"feed": feed}), 200


@agents_bp.route("/api/agents/<path:agent_did>/tasks", methods=["POST"])
def submit_task(agent_did):
    state = current_app.app_state
    if agent_did not in state.agent_registry:
        return jsonify({"error": "Agent not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    description = data.get("description")
    if not description:
        return jsonify({"error": "Missing description"}), 400
    task = AgentTask(
        description=description,
        payload=data.get("payload", {}),
    )
    agent = state.agent_registry[agent_did]
    task_id = agent.submit_task(task)
    executed = agent.run_next_task()
    result_task = executed if executed is not None else task
    return jsonify({"message": "Task submitted", "task": result_task.to_dict()}), 201


@agents_bp.route("/api/agents/<path:agent_did>/tasks", methods=["GET"])
def list_tasks(agent_did):
    state = current_app.app_state
    if agent_did not in state.agent_registry:
        return jsonify({"error": "Agent not found"}), 404
    agent = state.agent_registry[agent_did]
    tasks = [t.to_dict() for t in agent.task_queue]
    return jsonify({"tasks": tasks}), 200
