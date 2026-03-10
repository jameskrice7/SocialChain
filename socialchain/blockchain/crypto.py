"""Cryptographic utility helpers that run behind the scenes.

Provides deterministic hashing, key-derivation, Merkle roots, and
signature-verification helpers used across the blockchain layer.
"""

import hashlib
import hmac
import json
import math
from typing import List, Optional


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def sha256(data: str) -> str:
    """Return hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def double_sha256(data: str) -> str:
    """SHA-256(SHA-256(data)) – used in Bitcoin-style block hashing."""
    first = hashlib.sha256(data.encode("utf-8")).digest()
    return hashlib.sha256(first).hexdigest()


def hmac_sha256(key: bytes, message: bytes) -> str:
    """HMAC-SHA256 keyed hash, returned as hex."""
    return hmac.new(key, message, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Key-derivation (PBKDF2) for password storage
# ---------------------------------------------------------------------------

_KDF_ITERATIONS = 100_000
_KDF_HASH = "sha256"
_SALT_LEN = 16  # bytes


def derive_key(password: str, salt: Optional[bytes] = None) -> tuple:
    """Derive a 32-byte key from *password* via PBKDF2-HMAC-SHA256.

    Returns ``(derived_hex, salt_hex)`` so both can be stored.
    """
    import os
    if salt is None:
        salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac(
        _KDF_HASH, password.encode("utf-8"), salt, _KDF_ITERATIONS, dklen=32
    )
    return dk.hex(), salt.hex()


def verify_key(password: str, derived_hex: str, salt_hex: str) -> bool:
    """Return ``True`` if *password* reproduces *derived_hex*."""
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac(
        _KDF_HASH, password.encode("utf-8"), salt, _KDF_ITERATIONS, dklen=32
    )
    return hmac.compare_digest(dk.hex(), derived_hex)


# ---------------------------------------------------------------------------
# Merkle tree
# ---------------------------------------------------------------------------

def merkle_root(hashes: List[str]) -> str:
    """Compute the Merkle root of a list of hex-encoded hashes.

    Uses SHA-256 pairing.  If the list has an odd number of elements the
    last element is duplicated.  An empty list returns 64 zero-chars.
    """
    if not hashes:
        return "0" * 64
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: List[str] = []
        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            next_level.append(sha256(combined))
        level = next_level
    return level[0]


# ---------------------------------------------------------------------------
# Difficulty / target helpers
# ---------------------------------------------------------------------------

def difficulty_target(difficulty: int) -> str:
    """Return the target hash string for a given difficulty level."""
    return "0" * difficulty + "f" * (64 - difficulty)


def hash_meets_difficulty(hash_hex: str, difficulty: int) -> bool:
    """Check whether *hash_hex* satisfies the given difficulty."""
    return hash_hex.startswith("0" * difficulty)


# ---------------------------------------------------------------------------
# Simple math helpers used in trust / reputation (non-visible background)
# ---------------------------------------------------------------------------

def sigmoid(x: float) -> float:
    """Standard logistic sigmoid σ(x) = 1 / (1 + e^{-x})."""
    return 1.0 / (1.0 + math.exp(-x))


def log_scale(value: float, base: float = 10.0) -> float:
    """Logarithmic scaling: log_base(1 + |value|), preserving sign."""
    if value == 0:
        return 0.0
    sign = 1 if value > 0 else -1
    return sign * math.log(1 + abs(value)) / math.log(base)


def weighted_average(values: List[float], weights: List[float]) -> float:
    """Return weighted average, or 0.0 when weights sum to zero."""
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    return sum(v * w for v, w in zip(values, weights)) / total_weight
