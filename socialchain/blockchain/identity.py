import hashlib
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


class Identity:
    def __init__(self, private_key=None):
        if private_key is None:
            self._private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        else:
            self._private_key = private_key
        self._public_key = self._private_key.public_key()
        self.did = self._compute_did()

    def _compute_did(self) -> str:
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint,
        )
        hex_pub = pub_bytes.hex()
        return f"did:socialchain:{hex_pub}"

    def sign(self, message: bytes) -> str:
        signature = self._private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        return signature.hex()

    def verify(self, message: bytes, signature_hex: str) -> bool:
        try:
            sig_bytes = bytes.fromhex(signature_hex)
            self._public_key.verify(sig_bytes, message, ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError):
            return False

    def public_key_hex(self) -> str:
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint,
        )
        return pub_bytes.hex()

    def to_dict(self) -> dict:
        return {"did": self.did, "public_key": self.public_key_hex()}

    def __repr__(self) -> str:
        return f"Identity(did={self.did})"
