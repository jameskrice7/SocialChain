from enum import Enum
from typing import Any, Dict, Optional


class DeviceType(str, Enum):
    HUMAN = "human"
    DEVICE = "device"
    AGENT = "agent"


class Profile:
    def __init__(
        self,
        did: str,
        display_name: str,
        device_type: DeviceType = DeviceType.HUMAN,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.did = did
        self.display_name = display_name
        self.device_type = DeviceType(device_type)
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "did": self.did,
            "display_name": self.display_name,
            "device_type": self.device_type.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return cls(
            did=d["did"],
            display_name=d["display_name"],
            device_type=DeviceType(d.get("device_type", "human")),
            metadata=d.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"Profile(did={self.did[:32]}..., name={self.display_name}, type={self.device_type})"
