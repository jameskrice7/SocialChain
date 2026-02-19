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
    agent.run_next_task()
    return jsonify({"message": "Task submitted", "task": task.to_dict()}), 201


@agents_bp.route("/api/agents/<path:agent_did>/tasks", methods=["GET"])
def list_tasks(agent_did):
    state = current_app.app_state
    if agent_did not in state.agent_registry:
        return jsonify({"error": "Agent not found"}), 404
    agent = state.agent_registry[agent_did]
    tasks = [t.to_dict() for t in agent.task_queue]
    return jsonify({"tasks": tasks}), 200
