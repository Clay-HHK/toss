"""Client-side end-to-end encryption primitives (Tier 2 Phase A).

This package is *opt-in*. Importing it requires PyNaCl to be installed. It is
not wired into the default push/pull path yet — the Phase A goal is to make
keypair creation, enrollment, and standalone encrypt/decrypt roundtrips work,
so later phases can flip the default without further API churn.
"""

from .encrypt import decrypt_as_recipient, encrypt_for_recipients
from .header import MAGIC, VERSION, FileHeader, pack_header, unpack_header
from .keypair import KeyPair, fingerprint_from_public_key
from .keystore import EnvKeyStore, FileKeyStore, KeyStore, KeyStoreError, auto_detect_keystore

__all__ = [
    "KeyPair",
    "fingerprint_from_public_key",
    "MAGIC",
    "VERSION",
    "FileHeader",
    "pack_header",
    "unpack_header",
    "encrypt_for_recipients",
    "decrypt_as_recipient",
    "KeyStore",
    "KeyStoreError",
    "EnvKeyStore",
    "FileKeyStore",
    "auto_detect_keystore",
]
