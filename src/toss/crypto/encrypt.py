"""Encrypt / decrypt helpers for TOSS v2 blobs.

One content key per file, wrapped per recipient. This is the classic
hybrid-encryption pattern and keeps the fan-out cost O(N) in wrap size
while the body only pays one AEAD pass.

Threat model (Phase A):
- **Attacker-in-the-middle**: sees only ciphertext + header. Cannot read body
  without a recipient's private key.
- **Malicious recipient**: can decrypt their own copy and could re-share the
  plaintext — we do not try to prevent that.
- **Malicious sender**: the header is self-authenticated via each recipient's
  libsodium Box MAC (sender_sk + recipient_pk), so tampering in transit is
  detected on decrypt. This is authenticated encryption with sender identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from nacl import public, secret
from nacl.exceptions import CryptoError
from nacl.utils import random as nacl_random

from .header import (
    CONTENT_NONCE_SIZE,
    WRAPPED_KEY_SIZE,
    FileHeader,
    HeaderError,
    WrappedRecipient,
    pack_header,
    unpack_header,
)
from .keypair import KeyPair

_CONTENT_KEY_SIZE = secret.SecretBox.KEY_SIZE  # 32
_WRAP_NONCE_SIZE = public.Box.NONCE_SIZE  # 24


class DecryptError(ValueError):
    """Raised when a ciphertext cannot be decrypted by any supplied keypair."""


@dataclass(frozen=True)
class EncryptedBlob:
    """Container holding the packed header+body bytes."""

    bytes_: bytes

    def __len__(self) -> int:
        return len(self.bytes_)


def encrypt_for_recipients(
    plaintext: bytes,
    filename: str,
    sender: KeyPair,
    recipient_public_keys: Sequence[bytes],
) -> bytes:
    """Encrypt `plaintext` so each recipient can decrypt it with their X25519 key.

    :param plaintext: raw file bytes
    :param filename: original filename (stored *in the header* so recipients can
        restore it). In Phase A this is always plain UTF-8.
    :param sender: sender's :class:`KeyPair` — needs the private key to wrap
    :param recipient_public_keys: list of 32-byte X25519 public keys

    :returns: packed header + body ciphertext as a single ``bytes`` blob
    :raises ValueError: if inputs are malformed
    """
    if not recipient_public_keys:
        raise ValueError("at least one recipient is required")

    # 1. Draw a fresh 32-byte content key + 24-byte body nonce.
    content_key = nacl_random(_CONTENT_KEY_SIZE)
    content_nonce = nacl_random(CONTENT_NONCE_SIZE)

    # 2. Body is SecretBox(content_key)(plaintext, content_nonce). We store
    #    the nonce separately in the header and persist only the ciphertext
    #    (ct || poly1305 tag) here.
    body_box = secret.SecretBox(content_key)
    body_enc = body_box.encrypt(plaintext, content_nonce)
    body_ct = body_enc.ciphertext

    # 3. Wrap content_key to every recipient with a fresh nonce each.
    sender_sk = sender.encryption_private_key
    wrapped: list[WrappedRecipient] = []
    for r_pk in recipient_public_keys:
        if len(r_pk) != 32:
            raise ValueError(f"recipient public key must be 32 bytes, got {len(r_pk)}")
        wrap_box = public.Box(sender_sk, public.PublicKey(r_pk))
        wrap_nonce = nacl_random(_WRAP_NONCE_SIZE)
        wrap_enc = wrap_box.encrypt(content_key, wrap_nonce)
        # wrap_enc.nonce (24) + wrap_enc.ciphertext (48) = 72 bytes
        wrapped_blob = bytes(wrap_enc.nonce) + bytes(wrap_enc.ciphertext)
        if len(wrapped_blob) != WRAPPED_KEY_SIZE:
            raise RuntimeError(
                f"unexpected wrapped key size {len(wrapped_blob)}; expected {WRAPPED_KEY_SIZE}",
            )
        wrapped.append(WrappedRecipient(public_key=bytes(r_pk), wrapped_key=wrapped_blob))

    header = FileHeader(
        sender_pub=sender.encryption_public_bytes,
        filename=filename.encode("utf-8"),
        recipients=wrapped,
        content_nonce=content_nonce,
        filename_encrypted=False,
    )

    return pack_header(header) + body_ct


def decrypt_as_recipient(
    blob: bytes,
    recipient_keys: Sequence[KeyPair],
    expected_sender_public_key: bytes | None = None,
) -> tuple[bytes, str]:
    """Decrypt a TOSS v2 blob as the holder of one of ``recipient_keys``.

    Tries each supplied keypair in order; this lets callers pass the current
    key plus any historical keys when decrypting old blobs after a rotation.

    :param blob: full header + body bytes
    :param recipient_keys: one or more candidate :class:`KeyPair` holders
    :param expected_sender_public_key: if given, decryption fails unless the
        header's sender pubkey matches. Use this to pin a verified contact.

    :returns: ``(plaintext, filename)``
    :raises DecryptError: if the blob cannot be parsed or unwrapped by any key
    """
    if not recipient_keys:
        raise DecryptError("no recipient keys supplied")

    try:
        header, body_offset = unpack_header(blob)
    except HeaderError as e:
        raise DecryptError(f"invalid header: {e}") from e

    if (
        expected_sender_public_key is not None
        and bytes(expected_sender_public_key) != header.sender_pub
    ):
        raise DecryptError("sender public key does not match expected")

    body_ct = blob[body_offset:]

    last_error: Exception | None = None
    for kp in recipient_keys:
        my_pub = kp.encryption_public_bytes
        match = next((r for r in header.recipients if r.public_key == my_pub), None)
        if match is None:
            continue
        try:
            wrap_box = public.Box(
                kp.encryption_private_key,
                public.PublicKey(header.sender_pub),
            )
            content_key = wrap_box.decrypt(match.wrapped_key)
            body_box = secret.SecretBox(content_key)
            plaintext = body_box.decrypt(body_ct, header.content_nonce)
        except CryptoError as e:
            last_error = e
            continue

        filename = header.filename.decode("utf-8", errors="replace")
        return plaintext, filename

    if last_error is not None:
        raise DecryptError(f"no matching recipient key could decrypt blob: {last_error}")
    raise DecryptError("no matching recipient key in header")
