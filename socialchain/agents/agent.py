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
        self._handlers["chat"] = self._handle_chat
        self._handlers["autonomous_post"] = self._handle_autonomous_post

    def _handle_chat(self, payload: dict) -> dict:
        """Rule-based IDE assistant; replace handler with an LLM for richer responses."""
        message = payload.get("message", "")
        msg_lower = message.lower()

        if any(w in msg_lower for w in ("hello", "hi", "hey")):
            reply = (
                f"Hello! I'm {self.name}, your SocialChain IDE assistant. "
                "I can help you write, audit, and deploy smart contracts, "
                "explore the blockchain, or navigate the social network."
            )
        elif any(w in msg_lower for w in ("solidity", "contract", "pragma", "evm", "abi", "bytecode")):
            reply = (
                "SocialChain's IDE supports Solidity smart contracts. "
                "Use the **IDE** tab to write and compile contracts. "
                "Contracts are deployed as signed blockchain transactions using your DID key-pair — "
                "no external wallet required."
            )
        elif any(w in msg_lower for w in ("deploy", "deployment", "compile")):
            reply = (
                "To deploy a contract: open the IDE, paste your Solidity source, "
                "click **Compile**, then **Deploy**. "
                "The deployment transaction is signed with your secp256k1 identity and "
                "broadcast to the SocialChain network."
            )
        elif any(w in msg_lower for w in ("audit", "security", "vuln", "reentrancy", "overflow")):
            reply = (
                "I can flag common Solidity vulnerabilities: reentrancy, integer overflow, "
                "unchecked call return values, and improper access control. "
                "Paste your contract source and ask me to audit it."
            )
        elif any(w in msg_lower for w in ("transaction", "tx", "block", "chain", "hash", "mine")):
            reply = (
                "Every interaction on SocialChain — profile updates, connections, deployments — "
                "is an ECDSA-signed transaction recorded on the SHA-256 proof-of-work chain. "
                "Use the Dashboard to mine pending transactions into a new block."
            )
        elif any(w in msg_lower for w in ("did", "identity", "key", "wallet", "address")):
            reply = (
                "Your DID (Decentralized Identifier) is derived from your secp256k1 public key: "
                "`did:socialchain:<compressed-pubkey-hex>`. "
                "It acts as your wallet address, signing key, and social identity — all in one."
            )
        elif any(w in msg_lower for w in ("agent", "autonomous", "bot")):
            reply = (
                f"I'm {self.name}, a blockchain-registered autonomous agent "
                f"(DID: {self.did[:32]}…). "
                f"My registered capabilities are: {', '.join(self.capabilities)}. "
                "Autonomous agents can submit transactions, audit contracts, and post "
                "network status updates without human intervention."
            )
        elif any(w in msg_lower for w in ("network", "peer", "node", "p2p")):
            reply = (
                "The SocialChain P2P network connects nodes via HTTP broadcast. "
                "Every node shares the same chain via consensus. "
                "Visit the **Network** view to visualise the live node graph."
            )
        elif any(w in msg_lower for w in ("help", "what can you", "capabilit")):
            caps = ", ".join(self.capabilities) if self.capabilities else "echo, chat"
            reply = (
                f"I can assist with: {caps}. "
                "Try asking me to: audit a Solidity contract, explain a transaction, "
                "describe the DID identity model, or walk you through deploying a contract."
            )
        elif "?" in message:
            reply = (
                "Great question! I specialise in blockchain development on SocialChain. "
                "Ask me about smart contracts, transactions, identity (DID), "
                "network topology, or agent deployment."
            )
        else:
            reply = (
                f"Noted. I'm {self.name}, your on-chain IDE assistant. "
                "I can help with smart contract development, chain exploration, "
                "identity management, and autonomous agent tasks. "
                "What would you like to work on?"
            )
        return {"reply": reply, "agent": self.name, "agent_did": self.did}

    def _handle_autonomous_post(self, payload: dict) -> dict:
        topic = payload.get("topic", "network")
        posts = {
            "network": (
                f"🔗 Agent {self.name}: Network topology is stable. "
                "New node connections detected across the mesh."
            ),
            "blockchain": (
                f"⛓ Agent {self.name}: Block finalised. All pending social "
                "interactions are now immutably recorded on-chain."
            ),
            "contract": (
                f"📄 Agent {self.name}: New smart contract deployment verified. "
                "ABI and bytecode anchored to block hash."
            ),
            "audit": (
                f"🔍 Agent {self.name}: Contract audit complete. "
                "No critical vulnerabilities detected. Report appended to chain."
            ),
        }
        content = posts.get(topic, f"🤖 Agent {self.name} is active on the SocialChain network.")
        return {"post": content, "agent": self.name, "topic": topic}

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
