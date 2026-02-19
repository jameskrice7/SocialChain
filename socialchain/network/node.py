import json
import logging
from typing import Any, Dict, List, Optional

import requests

from .registry import PeerRegistry
from ..blockchain.identity import Identity
from ..blockchain.blockchain import Blockchain

logger = logging.getLogger(__name__)


class NetworkNode:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, identity: Optional[Identity] = None):
        self.identity = identity or Identity()
        self.node_id = self.identity.did
        self.host = host
        self.port = port
        self.registry = PeerRegistry()

    def register_peer(self, did: str, address: str) -> None:
        self.registry.add(did, address)

    def remove_peer(self, did: str) -> bool:
        return self.registry.remove(did)

    def get_peers(self) -> Dict[str, str]:
        return self.registry.list()

    def broadcast(self, endpoint: str, data: dict) -> List[dict]:
        results = []
        for did, address in self.registry.list().items():
            url = f"http://{address}{endpoint}"
            try:
                response = requests.post(url, json=data, timeout=5)
                results.append({"did": did, "status": response.status_code, "data": response.json()})
            except Exception as e:
                logger.warning(f"Failed to broadcast to {did} at {url}: {e}")
                results.append({"did": did, "status": None, "error": str(e)})
        return results

    def sync_chain(self, blockchain: Blockchain) -> bool:
        longest_chain = None
        max_length = len(blockchain.chain)
        for did, address in self.registry.list().items():
            url = f"http://{address}/api/chain"
            try:
                response = requests.get(url, timeout=5)
                data = response.json()
                if data["length"] > max_length:
                    max_length = data["length"]
                    longest_chain = data
            except Exception as e:
                logger.warning(f"Failed to sync with {did}: {e}")
        if longest_chain:
            # Replace the local chain with the longer one from peers
            from ..blockchain.block import Block
            from ..blockchain.transaction import Transaction
            new_chain = []
            for block_data in longest_chain["chain"]:
                txs = [Transaction.from_dict(tx) for tx in block_data["transactions"]]
                block = Block(
                    index=block_data["index"],
                    transactions=txs,
                    previous_hash=block_data["previous_hash"],
                    nonce=block_data["nonce"],
                    timestamp=block_data["timestamp"],
                )
                block.hash = block_data["hash"]
                new_chain.append(block)
            blockchain.chain = new_chain
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "peers": self.registry.list(),
        }

    def __repr__(self) -> str:
        return f"NetworkNode(id={self.node_id[:32]}..., host={self.host}, port={self.port})"
