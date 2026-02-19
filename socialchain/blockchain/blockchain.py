from typing import List, Optional
from .block import Block
from .transaction import Transaction


class Blockchain:
    DIFFICULTY = 4

    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = Block(index=0, transactions=[], previous_hash="0" * 64)
        genesis.nonce, genesis.hash = self._proof_of_work(genesis)
        self.chain.append(genesis)

    def _proof_of_work(self, block: Block):
        nonce = 0
        block.nonce = nonce
        computed = block.compute_hash()
        while not computed.startswith("0" * self.DIFFICULTY):
            nonce += 1
            block.nonce = nonce
            computed = block.compute_hash()
        return nonce, computed

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: Transaction) -> int:
        self.pending_transactions.append(transaction)
        return self.last_block.index + 1

    def mine_block(self, miner_did: str) -> Block:
        reward_tx = Transaction(
            sender="NETWORK",
            recipient=miner_did,
            data={"reward": 1, "type": "mining_reward"},
        )
        self.pending_transactions.append(reward_tx)
        block = Block(
            index=len(self.chain),
            transactions=list(self.pending_transactions),
            previous_hash=self.last_block.hash,
        )
        nonce, block_hash = self._proof_of_work(block)
        block.nonce = nonce
        block.hash = block_hash
        self.chain.append(block)
        self.pending_transactions = []
        return block

    def add_block(self, block: Block) -> bool:
        if block.previous_hash != self.last_block.hash:
            return False
        if not block.hash.startswith("0" * self.DIFFICULTY):
            return False
        if block.hash != block.compute_hash():
            return False
        self.chain.append(block)
        return True

    def validate_chain(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith("0" * self.DIFFICULTY):
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "chain": [block.to_dict() for block in self.chain],
            "length": len(self.chain),
            "pending_transactions": [tx.to_dict() for tx in self.pending_transactions],
        }

    def __repr__(self) -> str:
        return f"Blockchain(length={len(self.chain)}, pending={len(self.pending_transactions)})"
