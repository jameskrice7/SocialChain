"""One observable background mining run per in-memory ledger."""
import logging
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4


class MiningCancelled(Exception):
    pass


class MinerBusy(Exception):
    pass


class MiningJob:
    ACTIVE = {"starting", "running", "cancelling", "committing"}

    def __init__(self, owner, limit):
        self.id = str(uuid4())
        self.owner = owner
        self.limit = limit
        self._lock = Lock()
        self._state = "starting"
        self._started = monotonic()
        self._ended = None
        self._attempts = 0
        self._index = None
        self._count = 0
        self._hash = None

    def _check_cancelled(self):
        if self._state == "cancelling":
            raise MiningCancelled()

    def begin_candidate(self, index, count):
        with self._lock:
            self._check_cancelled()
            self._state = "running"
            self._index = index
            self._count = count

    def record(self, attempts):
        with self._lock:
            self._attempts += attempts
            self._check_cancelled()

    def begin_commit(self):
        with self._lock:
            self._check_cancelled()
            self._state = "committing"

    def cancel(self):
        with self._lock:
            if self._state in {"starting", "running"}:
                self._state = "cancelling"
            return self._state in {"cancelling", "cancelled"}

    def finish(self, state, block=None):
        with self._lock:
            self._state = "cancelled" if self._state == "cancelling" else state
            self._ended = monotonic()
            self._hash = block.hash if block else None

    def snapshot(self):
        with self._lock:
            elapsed = (self._ended or monotonic()) - self._started
            return {
                "id": self.id, "miner_did": self.owner, "limit": self.limit,
                "state": self._state, "active": self._state in self.ACTIVE,
                "attempts": self._attempts, "elapsed_seconds": round(elapsed, 3),
                "hashes_per_second": round(self._attempts / elapsed) if elapsed else 0,
                "block_index": self._index, "transaction_count": self._count,
                "block_hash": self._hash,
            }


class MiningService:
    def __init__(self, ledger):
        self.ledger = ledger
        self._lock = Lock()
        self._latest = None

    def latest(self):
        with self._lock:
            return self._latest

    def start(self, owner, limit):
        with self._lock:
            if self._latest and self._latest.snapshot()["active"]:
                raise MinerBusy()
            if not self.ledger.summary()["pending_count"]:
                raise ValueError("No pending transactions to mine")
            job = MiningJob(owner, limit)
            self._latest = job
            try:
                Thread(target=self._run, args=(job,), daemon=True, name="socialchain-miner").start()
            except RuntimeError:
                job.finish("failed")
                raise
            return job

    def _run(self, job):
        try:
            block = self.ledger.mine_block(job.owner, require_pending=True, limit=job.limit, job=job)
            job.finish("completed" if block else "empty", block)
        except MiningCancelled:
            job.finish("cancelled")
        except MinerBusy:
            job.finish("busy")
        except Exception:
            logging.getLogger(__name__).exception("Background mining failed")
            job.finish("failed")
