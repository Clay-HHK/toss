"""User keypair — one Ed25519 seed, two derived keys.

Toss uses:
- **Ed25519** for signing proofs (enrollment) and future message authentication
- **X25519** for encryption (Box from Ed25519's Curve25519 form)

Instead of managing two independent 32-byte seeds, we store a single Ed25519
seed and derive the X25519 private key on demand. This halves the secret
surface the user has to back up.

Public keys are exposed as text strings with version prefixes so a leaked
public key is obviously a public key (and cannot be mistaken for a secret):
- Encryption pubkey: ``toss1<base64url>``
- Signing pubkey:    ``tossk1<base64url>``

Fingerprints are a short BLAKE2b-8 hex for human comparison (e.g. over a
phone call). They are NOT cryptographic commitments — they are UX only.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from nacl import public, signing
from nacl.utils import random as nacl_random

ENCRYPT_PREFIX = "toss1"
SIGNING_PREFIX = "tossk1"
SEED_SIZE = 32


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _strip_prefix(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise ValueError(f"Expected prefix '{prefix}', got: {value[:10]}...")
    return value[len(prefix):]


def fingerprint_from_public_key(public_key_bytes: bytes) -> str:
    """Short human-comparable fingerprint: 8 bytes of BLAKE2b, colon-separated hex."""
    digest = hashlib.blake2b(public_key_bytes, digest_size=8).hexdigest()
    return ":".join(digest[i : i + 2] for i in range(0, 16, 2))


@dataclass(frozen=True)
class KeyPair:
    """One Ed25519 seed, exposing Ed25519 signing + X25519 encryption pairs.

    Instances are frozen and small. Copies are cheap. The raw seed is kept in
    the instance so callers can persist it — do not log this object.
    """

    seed: bytes

    def __post_init__(self) -> None:
        if len(self.seed) != SEED_SIZE:
            raise ValueError(f"seed must be {SEED_SIZE} bytes, got {len(self.seed)}")

    # --- factories -----------------------------------------------------------

    @classmethod
    def generate(cls) -> "KeyPair":
        """Create a fresh keypair from OS entropy."""
        return cls(seed=nacl_random(SEED_SIZE))

    @classmethod
    def from_seed(cls, seed: bytes) -> "KeyPair":
        return cls(seed=seed)

    @classmethod
    def from_seed_b64(cls, seed_b64: str) -> "KeyPair":
        return cls(seed=_b64u_decode(seed_b64))

    # --- key material --------------------------------------------------------

    @property
    def signing_key(self) -> signing.SigningKey:
        return signing.SigningKey(self.seed)

    @property
    def verify_key(self) -> signing.VerifyKey:
        return self.signing_key.verify_key

    @property
    def encryption_private_key(self) -> public.PrivateKey:
        # Derive X25519 private from Ed25519 via libsodium's documented path.
        return self.signing_key.to_curve25519_private_key()

    @property
    def encryption_public_key(self) -> public.PublicKey:
        return self.encryption_private_key.public_key

    @property
    def encryption_public_bytes(self) -> bytes:
        return bytes(self.encryption_public_key)

    @property
    def signing_public_bytes(self) -> bytes:
        return bytes(self.verify_key)

    # --- text encoding -------------------------------------------------------

    def encryption_public_str(self) -> str:
        return ENCRYPT_PREFIX + _b64u_encode(self.encryption_public_bytes)

    def signing_public_str(self) -> str:
        return SIGNING_PREFIX + _b64u_encode(self.signing_public_bytes)

    def seed_b64(self) -> str:
        """Base64url-encoded seed for backup / export. Handle with care."""
        return _b64u_encode(self.seed)

    def fingerprint(self) -> str:
        return fingerprint_from_public_key(self.encryption_public_bytes)

    # --- operations ----------------------------------------------------------

    def sign(self, message: bytes) -> bytes:
        """Return a detached 64-byte Ed25519 signature over `message`."""
        return self.signing_key.sign(message).signature


def parse_encryption_public_key(value: str) -> bytes:
    """Decode a ``toss1...`` string back to the 32-byte X25519 public key."""
    return _b64u_decode(_strip_prefix(value, ENCRYPT_PREFIX))


def parse_signing_public_key(value: str) -> bytes:
    """Decode a ``tossk1...`` string back to the 32-byte Ed25519 public key."""
    return _b64u_decode(_strip_prefix(value, SIGNING_PREFIX))
