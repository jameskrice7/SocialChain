from typing import Dict, List, Optional, Tuple
from .profile import Profile


class NetworkMap:
    def __init__(self):
        self._profiles: Dict[str, Profile] = {}
        self._connections: Dict[str, List[str]] = {}  # did -> list of connected dids

    def add_profile(self, profile: Profile) -> None:
        self._profiles[profile.did] = profile
        if profile.did not in self._connections:
            self._connections[profile.did] = []

    def remove_profile(self, did: str) -> bool:
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
        if did_a not in self._profiles or did_b not in self._profiles:
            return False
        if did_b not in self._connections[did_a]:
            self._connections[did_a].append(did_b)
        if did_a not in self._connections[did_b]:
            self._connections[did_b].append(did_a)
        return True

    def get_connections(self, did: str) -> List[str]:
        return self._connections.get(did, [])

    def visualize(self) -> Dict[str, List[str]]:
        return {did: list(conns) for did, conns in self._connections.items()}

    def list_profiles(self) -> List[Profile]:
        return list(self._profiles.values())

    def __repr__(self) -> str:
        return f"NetworkMap(profiles={len(self._profiles)}, connections={sum(len(v) for v in self._connections.values())})"
