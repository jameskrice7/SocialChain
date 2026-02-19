import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class AgentTask:
    description: str
    payload: Dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.QUEUED
    result: Optional[Any] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "payload": self.payload,
            "status": self.status.value,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentTask":
        return cls(
            description=d["description"],
            payload=d.get("payload", {}),
            task_id=d.get("task_id", str(uuid.uuid4())),
            status=TaskStatus(d.get("status", "QUEUED")),
            result=d.get("result"),
        )
