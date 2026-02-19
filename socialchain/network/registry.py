from typing import Dict, List, Optional


class PeerRegistry:
    def __init__(self):
        self._peers: Dict[str, str] = {}  # did -> host:port

    def add(self, did: str, address: str) -> None:
        self._peers[did] = address

    def remove(self, did: str) -> bool:
        if did in self._peers:
            del self._peers[did]
            return True
        return False

    def list(self) -> Dict[str, str]:
        return dict(self._peers)

    def get(self, did: str) -> Optional[str]:
        return self._peers.get(did)

    def __len__(self) -> int:
        return len(self._peers)

    def __repr__(self) -> str:
        return f"PeerRegistry(peers={len(self._peers)})"
