from collections import deque
from threading import Lock
from typing import Dict, List, Optional
from .profile import Profile


class NetworkMap:
    def __init__(self):
        self._lock = Lock()
        self._profiles: Dict[str, Profile] = {}
        self._connections: Dict[str, List[str]] = {}  # did -> list of connected dids

    def add_profile(self, profile: Profile) -> None:
        with self._lock:
            self._profiles[profile.did] = profile
            if profile.did not in self._connections:
                self._connections[profile.did] = []

    def remove_profile(self, did: str) -> bool:
        with self._lock:
            if did in self._profiles:
                del self._profiles[did]
                self._connections.pop(did, None)
                for connections in self._connections.values():
                    if did in connections:
                        connections.remove(did)
                return True
            return False

    def get_profile(self, did: str) -> Optional[Profile]:
        return self._profiles.get(did)

    def add_connection(self, did_a: str, did_b: str) -> bool:
        with self._lock:
            if did_a not in self._profiles or did_b not in self._profiles:
                return False
            if did_b not in self._connections[did_a]:
                self._connections[did_a].append(did_b)
            if did_a not in self._connections[did_b]:
                self._connections[did_b].append(did_a)
            return True

    def get_connections(self, did: str) -> List[str]:
        with self._lock:
            return list(self._connections.get(did, []))

    def visualize(self) -> Dict[str, List[str]]:
        with self._lock:
            return {did: list(conns) for did, conns in self._connections.items()}

    def list_profiles(self) -> List[Profile]:
        with self._lock:
            return list(self._profiles.values())

    def connection_path(self, source: str, target: str, avoid: Optional[str] = None) -> dict:
        """Compare shortest paths using one snapshot of the profile connections."""
        graph = self.visualize()
        for did in (source, target, avoid):
            if did is not None and did not in graph:
                raise KeyError(did)
        if avoid in (source, target):
            raise ValueError("Choose an intermediary other than the start or destination")

        def traverse(excluded):
            parents = {source: None}
            queue = deque([source])
            while queue:
                current = queue.popleft()
                # Equal-length routes are resolved by DID, independently of insertion order.
                for neighbor in sorted(graph[current]):
                    if neighbor != excluded and neighbor not in parents:
                        parents[neighbor] = current
                        queue.append(neighbor)
            path = []
            node = target if target in parents else None
            while node is not None:
                path.append(node)
                node = parents[node]
            path.reverse()
            return {"path": path, "hops": len(path) - 1 if path else None,
                    "reachable_profiles": len(parents) - 1}

        return {
            "source": source, "target": target, "avoid": avoid,
            "baseline": traverse(None),
            "scenario": traverse(avoid) if avoid is not None else None,
        }

    def __repr__(self) -> str:
        with self._lock:
            return f"NetworkMap(profiles={len(self._profiles)}, connections={sum(len(v) for v in self._connections.values())})"
