"""Binary header format for TOSS v2 encrypted blobs.

Every recipient gets a tiny per-recipient wrapped content key inside a single
header. The header is fully self-describing, so a stored blob does not need
any out-of-band metadata to be decrypted (the D1 row is just a hint).

Layout (little-endian throughout):

::

    0  +------------------+
       | Magic "TOSS"     | 4 bytes
       +------------------+
       | Version (0x02)   | 1 byte
       +------------------+
       | Flags            | 1 byte, bit 0 = filename encrypted
       +------------------+
       | Reserved         | 2 bytes (must be zero in v2)
       +------------------+
       | Sender X25519 pk | 32 bytes
       +------------------+
       | Filename length  | 2 bytes (N)
       +------------------+
       | Filename bytes   | N bytes (UTF-8, plain or sealed)
       +------------------+
       | Recipient count  | 2 bytes (M)
       +------------------+
       | Recipient 0      | 32 (pubkey) + 2 (len) + len bytes
       | ...              |
       | Recipient M-1    |
       +------------------+
       | Content nonce    | 24 bytes (SecretBox nonce for body)
       +------------------+  <-- content ciphertext starts here

The wrapped key length is variable only to future-proof against algorithm
changes. Today's only supported value is 72 bytes (Box nonce 24 + box ct 48).

Hard caps are enforced on parse to keep a malicious header from allocating
gigabytes: filename <= 1 KiB, recipients <= 1024, wrapped key <= 256 B.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"TOSS"
VERSION = 0x02
RESERVED = b"\x00\x00"

# Flag bits
FLAG_FILENAME_ENCRYPTED = 0x01

# Size constants
_SENDER_PUB_SIZE = 32
_RECIPIENT_PUB_SIZE = 32
CONTENT_NONCE_SIZE = 24
WRAPPED_KEY_SIZE = 72  # Box nonce (24) + ct (48)

# Sanity caps (apply on unpack only; pack validates against the same limits).
_MAX_FILENAME_LEN = 1024
_MAX_RECIPIENTS = 1024
_MAX_WRAPPED_KEY = 256


class HeaderError(ValueError):
    """Raised when the header is malformed, truncated, or uses an unknown version."""


@dataclass(frozen=True)
class WrappedRecipient:
    public_key: bytes  # 32-byte X25519
    wrapped_key: bytes  # libsodium Box (nonce || ct)


@dataclass(frozen=True)
class FileHeader:
    sender_pub: bytes  # 32-byte X25519
    filename: bytes  # UTF-8 bytes, plain or sealed
    recipients: list[WrappedRecipient] = field(default_factory=list)
    content_nonce: bytes = b""
    filename_encrypted: bool = False
    version: int = VERSION

    @property
    def flags(self) -> int:
        return FLAG_FILENAME_ENCRYPTED if self.filename_encrypted else 0


def pack_header(header: FileHeader) -> bytes:
    """Serialise `header` into its canonical byte layout."""
    if len(header.sender_pub) != _SENDER_PUB_SIZE:
        raise HeaderError(f"sender_pub must be {_SENDER_PUB_SIZE} bytes")
    if len(header.content_nonce) != CONTENT_NONCE_SIZE:
        raise HeaderError(f"content_nonce must be {CONTENT_NONCE_SIZE} bytes")
    if len(header.filename) > _MAX_FILENAME_LEN:
        raise HeaderError(f"filename too long: {len(header.filename)}")
    if len(header.recipients) == 0:
        raise HeaderError("header must have at least one recipient")
    if len(header.recipients) > _MAX_RECIPIENTS:
        raise HeaderError(f"too many recipients: {len(header.recipients)}")

    parts: list[bytes] = [
        MAGIC,
        struct.pack("<B", header.version),
        struct.pack("<B", header.flags),
        RESERVED,
        header.sender_pub,
        struct.pack("<H", len(header.filename)),
        header.filename,
        struct.pack("<H", len(header.recipients)),
    ]

    for r in header.recipients:
        if len(r.public_key) != _RECIPIENT_PUB_SIZE:
            raise HeaderError("recipient public key must be 32 bytes")
        if not (0 < len(r.wrapped_key) <= _MAX_WRAPPED_KEY):
            raise HeaderError(f"wrapped key size out of range: {len(r.wrapped_key)}")
        parts.append(r.public_key)
        parts.append(struct.pack("<H", len(r.wrapped_key)))
        parts.append(r.wrapped_key)

    parts.append(header.content_nonce)
    return b"".join(parts)


def unpack_header(blob: bytes) -> tuple[FileHeader, int]:
    """Parse a v2 header from the start of `blob`.

    Returns ``(header, body_offset)`` where ``blob[body_offset:]`` is the
    content ciphertext. Raises :class:`HeaderError` on any malformed input.
    """
    off = 0

    def _need(n: int) -> None:
        if off + n > len(blob):
            raise HeaderError(f"header truncated at offset {off}")

    _need(4)
    if blob[off : off + 4] != MAGIC:
        raise HeaderError("not a TOSS v2 blob (bad magic)")
    off += 4

    _need(1)
    version = blob[off]
    off += 1
    if version != VERSION:
        raise HeaderError(f"unsupported version: {version}")

    _need(1)
    flags = blob[off]
    off += 1
    filename_encrypted = bool(flags & FLAG_FILENAME_ENCRYPTED)

    _need(2)
    if blob[off : off + 2] != RESERVED:
        raise HeaderError("reserved bytes must be zero")
    off += 2

    _need(_SENDER_PUB_SIZE)
    sender_pub = blob[off : off + _SENDER_PUB_SIZE]
    off += _SENDER_PUB_SIZE

    _need(2)
    (filename_len,) = struct.unpack("<H", blob[off : off + 2])
    off += 2
    if filename_len > _MAX_FILENAME_LEN:
        raise HeaderError(f"filename length too big: {filename_len}")
    _need(filename_len)
    filename = blob[off : off + filename_len]
    off += filename_len

    _need(2)
    (recipient_count,) = struct.unpack("<H", blob[off : off + 2])
    off += 2
    if recipient_count == 0 or recipient_count > _MAX_RECIPIENTS:
        raise HeaderError(f"recipient count out of range: {recipient_count}")

    recipients: list[WrappedRecipient] = []
    for _ in range(recipient_count):
        _need(_RECIPIENT_PUB_SIZE + 2)
        r_pub = blob[off : off + _RECIPIENT_PUB_SIZE]
        off += _RECIPIENT_PUB_SIZE
        (wk_len,) = struct.unpack("<H", blob[off : off + 2])
        off += 2
        if not (0 < wk_len <= _MAX_WRAPPED_KEY):
            raise HeaderError(f"wrapped key size out of range: {wk_len}")
        _need(wk_len)
        wk = blob[off : off + wk_len]
        off += wk_len
        recipients.append(WrappedRecipient(public_key=r_pub, wrapped_key=wk))

    _need(CONTENT_NONCE_SIZE)
    content_nonce = blob[off : off + CONTENT_NONCE_SIZE]
    off += CONTENT_NONCE_SIZE

    header = FileHeader(
        sender_pub=sender_pub,
        filename=filename,
        recipients=recipients,
        content_nonce=content_nonce,
        filename_encrypted=filename_encrypted,
        version=version,
    )
    return header, off
