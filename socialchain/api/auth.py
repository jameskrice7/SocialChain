from werkzeug.security import generate_password_hash, check_password_hash
from ..blockchain.identity import Identity


class User:
    def __init__(self, username: str, password_hash: str, identity: "Identity", agent_type: str = "human"):
        self.username = username
        self.password_hash = password_hash
        self.identity = identity
        self.did = identity.did
        self.agent_type = agent_type  # "human" or "ai"

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "did": self.did,
            "agent_type": self.agent_type,
        }


def create_user(username: str, password: str, agent_type: str = "human") -> "User":
    identity = Identity()
    password_hash = generate_password_hash(password)
    return User(username=username, password_hash=password_hash, identity=identity, agent_type=agent_type)
