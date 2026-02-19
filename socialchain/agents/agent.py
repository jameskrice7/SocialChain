import json
from typing import Any, Callable, Dict, List, Optional

from ..blockchain.identity import Identity
from ..blockchain.transaction import Transaction
from ..blockchain.blockchain import Blockchain
from .task import AgentTask, TaskStatus


class AIAgent:
    def __init__(
        self,
        name: str,
        capabilities: Optional[List[str]] = None,
        identity: Optional[Identity] = None,
    ):
        self.name = name
        self.capabilities = capabilities or []
        self.identity = identity or Identity()
        self.did = self.identity.did
        self.task_queue: List[AgentTask] = []
        self._handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers["echo"] = lambda payload: {"echo": payload}
        self._handlers["store"] = lambda payload: {"stored": True, "key": payload.get("key")}

    def register_handler(self, capability: str, handler: Callable) -> None:
        self._handlers[capability] = handler
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def submit_task(self, task: AgentTask) -> str:
        self.task_queue.append(task)
        return task.task_id

    def execute_task(self, task: AgentTask) -> AgentTask:
        task.status = TaskStatus.RUNNING
        try:
            capability_key = task.payload.get("capability", "echo")
            handler = self._handlers.get(capability_key)
            if handler:
                task.result = handler(task.payload)
                task.status = TaskStatus.COMPLETED
            else:
                task.result = {"message": f"No handler for capability: {capability_key}"}
                task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.result = {"error": str(e)}
            task.status = TaskStatus.FAILED
        return task

    def run_next_task(self) -> Optional[AgentTask]:
        queued = [t for t in self.task_queue if t.status == TaskStatus.QUEUED]
        if not queued:
            return None
        return self.execute_task(queued[0])

    def register_on_blockchain(self, blockchain: Blockchain) -> Transaction:
        tx_data = {
            "type": "agent_registration",
            "name": self.name,
            "capabilities": self.capabilities,
            "did": self.did,
        }
        tx = Transaction(
            sender=self.did,
            recipient="NETWORK",
            data=tx_data,
        )
        announcement = json.dumps(tx.to_dict(), sort_keys=True).encode()
        tx.signature = self.identity.sign(announcement)
        blockchain.add_transaction(tx)
        return tx

    def to_dict(self) -> dict:
        return {
            "did": self.did,
            "name": self.name,
            "capabilities": self.capabilities,
            "task_count": len(self.task_queue),
        }

    def __repr__(self) -> str:
        return f"AIAgent(name={self.name}, did={self.did[:32]}..., capabilities={self.capabilities})"
