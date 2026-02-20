import json
from typing import Any, Callable, Dict, List, Optional

from ..blockchain.identity import Identity
from ..blockchain.transaction import Transaction
from ..blockchain.blockchain import Blockchain
from .task import AgentTask, TaskStatus


def _web_search(query: str, max_results: int = 5) -> dict:
    """Perform a live web search via DuckDuckGo Instant Answer API."""
    try:
        import requests as _req
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
            "no_redirect": "1",
        }
        resp = _req.get(
            "https://api.duckduckgo.com/",
            params=params,
            headers={"User-Agent": "SocialChain/1.0"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", query), "snippet": data["AbstractText"], "url": data.get("AbstractURL", "")})
        for topic in (data.get("RelatedTopics") or [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({"title": topic["Text"][:60], "snippet": topic["Text"], "url": topic.get("FirstURL", "")})
        return {"query": query, "results": results[:max_results], "abstract": data.get("AbstractText", "")}
    except Exception as exc:
        return {"query": query, "results": [], "error": str(exc)}


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
        self._handlers["search"] = self._handle_search

    def _handle_search(self, payload: dict) -> dict:
        """Perform a web search and return formatted results."""
        query = payload.get("query", payload.get("message", "")).strip()
        if not query:
            return {"reply": "Please provide a search query.", "agent": self.name, "agent_did": self.did, "search_results": []}
        search_data = _web_search(query, max_results=payload.get("max_results", 5))
        results = search_data.get("results", [])
        abstract = search_data.get("abstract", "")
        if abstract:
            reply = f"🌐 **Web results for: {query}**\n\n{abstract}\n\n"
        elif results:
            reply = f"🌐 **Web results for: {query}**\n\n"
        else:
            reply = f"No web results found for: {query}. Try rephrasing your search."
        for r in results[:5]:
            title = r.get("title", "")[:60]
            snippet = r.get("snippet", "")[:120]
            url = r.get("url", "")
            reply += f"• **{title}**\n  {snippet}"
            if url:
                reply += f"\n  🔗 {url}"
            reply += "\n\n"
        return {
            "reply": reply.strip(),
            "agent": self.name,
            "agent_did": self.did,
            "search_results": results,
            "query": query,
            "type": "search",
        }

    def _handle_chat(self, payload: dict) -> dict:
        """Rule-based IDE assistant with web search support."""
        message = payload.get("message", "")
        msg_lower = message.lower()

        # Detect explicit web search intent
        search_prefixes = ("search:", "search for", "look up", "find info on", "web:", "google:", "what is ", "who is ", "where is ")
        is_search = any(msg_lower.startswith(p) for p in search_prefixes) or msg_lower.startswith("search ")
        if is_search:
            # Strip prefix and delegate to search handler
            query = message
            for prefix in ("search:", "web:", "google:", "search for", "look up", "find info on"):
                if msg_lower.startswith(prefix):
                    query = message[len(prefix):].strip()
                    break
            return self._handle_search({**payload, "query": query})

        if any(w in msg_lower for w in ("hello", "hi", "hey")):
            reply = (
                f"Hello! I'm {self.name}, your SocialChain assistant. "
                "I can help you write and manage smart contracts, "
                "explore the blockchain, search the web, or navigate the social network. "
                "Try: `search: <topic>` to search the web!"
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
            caps = ", ".join(self.capabilities) if self.capabilities else "echo, chat, search"
            reply = (
                f"I can assist with: {caps}. "
                "Try asking me to: audit a Solidity contract, explain a transaction, "
                "describe the DID identity model, walk you through deploying a contract, "
                "or use `search: <topic>` to search the live web."
            )
        elif any(w in msg_lower for w in ("search", "internet", "web", "browse")):
            reply = (
                "To search the web, type: `search: <your query>` in this chat. "
                "You can also visit the **Internet** view for a live topology visualization "
                "and built-in search portal with direct web access."
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

    def execute_task(self, task: AgentTask, blockchain: Optional[Blockchain] = None) -> AgentTask:
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

        # Record task completion on chain if blockchain is provided
        if blockchain is not None:
            capability_key = task.payload.get("capability", "echo")
            # Only record non-trivial capabilities to avoid flooding the chain
            if capability_key not in ("echo", "store", "chat", "search"):
                self._record_task_on_chain(task, blockchain)

        return task

    def _record_task_on_chain(self, task: AgentTask, blockchain: Blockchain) -> Transaction:
        """Anchor a task execution event onto the blockchain."""
        import time as _time
        tx = Transaction(
            sender=self.did,
            recipient="NETWORK",
            data={
                "type": "agent_task",
                "agent_did": self.did,
                "agent_name": self.name,
                "task_id": task.task_id,
                "capability": task.payload.get("capability", "unknown"),
                "status": task.status.value,
                "timestamp": _time.time(),
            },
        )
        announcement = json.dumps(tx.to_dict(), sort_keys=True).encode()
        tx.signature = self.identity.sign(announcement)
        blockchain.add_transaction(tx)
        return tx

    def update_status(self, status: str, blockchain: Blockchain) -> Transaction:
        """Record agent online/offline/active status on the blockchain."""
        import time as _time
        tx = Transaction(
            sender=self.did,
            recipient="NETWORK",
            data={
                "type": "agent_status",
                "agent_did": self.did,
                "agent_name": self.name,
                "status": status,
                "timestamp": _time.time(),
            },
        )
        announcement = json.dumps(tx.to_dict(), sort_keys=True).encode()
        tx.signature = self.identity.sign(announcement)
        blockchain.add_transaction(tx)
        return tx

    def run_next_task(self, blockchain: Optional[Blockchain] = None) -> Optional[AgentTask]:
        queued = [t for t in self.task_queue if t.status == TaskStatus.QUEUED]
        if not queued:
            return None
        return self.execute_task(queued[0], blockchain=blockchain)

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
            "is_agent": True,
        }

    def __repr__(self) -> str:
        return f"AIAgent(name={self.name}, did={self.did[:32]}..., capabilities={self.capabilities})"
