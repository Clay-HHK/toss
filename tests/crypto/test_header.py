"""Tests for toss.crypto.header pack/unpack."""

import pytest

from toss.crypto.header import (
    CONTENT_NONCE_SIZE,
    MAGIC,
    VERSION,
    WRAPPED_KEY_SIZE,
    FileHeader,
    HeaderError,
    WrappedRecipient,
    pack_header,
    unpack_header,
)


def _dummy_recipient(byte: int = 1) -> WrappedRecipient:
    return WrappedRecipient(
        public_key=bytes([byte]) * 32,
        wrapped_key=bytes([byte]) * WRAPPED_KEY_SIZE,
    )


def _dummy_header(num_recipients: int = 2, filename: bytes = b"note.txt") -> FileHeader:
    return FileHeader(
        sender_pub=bytes([0xAA]) * 32,
        filename=filename,
        recipients=[_dummy_recipient(i + 1) for i in range(num_recipients)],
        content_nonce=bytes([0xBB]) * CONTENT_NONCE_SIZE,
        filename_encrypted=False,
    )


def test_pack_starts_with_magic_and_version() -> None:
    blob = pack_header(_dummy_header())
    assert blob[:4] == MAGIC
    assert blob[4] == VERSION
    assert blob[5] == 0  # flags
    assert blob[6:8] == b"\x00\x00"  # reserved


def test_round_trip_preserves_fields() -> None:
    original = _dummy_header(num_recipients=3, filename="中文.md".encode("utf-8"))
    packed = pack_header(original)
    restored, body_offset = unpack_header(packed + b"BODY")
    assert restored.sender_pub == original.sender_pub
    assert restored.filename == original.filename
    assert len(restored.recipients) == 3
    for got, want in zip(restored.recipients, original.recipients):
        assert got.public_key == want.public_key
        assert got.wrapped_key == want.wrapped_key
    assert restored.content_nonce == original.content_nonce
    assert packed[body_offset:] == b""
    assert (packed + b"BODY")[body_offset:] == b"BODY"


def test_flags_filename_encrypted_bit() -> None:
    h = FileHeader(
        sender_pub=bytes([0xAA]) * 32,
        filename=b"opaque",
        recipients=[_dummy_recipient()],
        content_nonce=bytes([0xBB]) * CONTENT_NONCE_SIZE,
        filename_encrypted=True,
    )
    blob = pack_header(h)
    assert blob[5] == 0x01
    restored, _ = unpack_header(blob)
    assert restored.filename_encrypted is True


def test_reject_bad_magic() -> None:
    blob = pack_header(_dummy_header())
    bad = b"XXXX" + blob[4:]
    with pytest.raises(HeaderError, match="magic"):
        unpack_header(bad)


def test_reject_unsupported_version() -> None:
    blob = pack_header(_dummy_header())
    bad = blob[:4] + bytes([0xFF]) + blob[5:]
    with pytest.raises(HeaderError, match="version"):
        unpack_header(bad)


def test_reject_truncated_header() -> None:
    blob = pack_header(_dummy_header())
    with pytest.raises(HeaderError, match="truncated"):
        unpack_header(blob[:10])


def test_reject_zero_recipients() -> None:
    with pytest.raises(HeaderError, match="at least one recipient"):
        pack_header(
            FileHeader(
                sender_pub=bytes([0xAA]) * 32,
                filename=b"",
                recipients=[],
                content_nonce=bytes([0xBB]) * CONTENT_NONCE_SIZE,
            ),
        )


def test_reject_wrong_sender_key_size() -> None:
    with pytest.raises(HeaderError):
        pack_header(
            FileHeader(
                sender_pub=b"\x00" * 31,
                filename=b"x",
                recipients=[_dummy_recipient()],
                content_nonce=bytes([0xBB]) * CONTENT_NONCE_SIZE,
            ),
        )
