"""End-to-end encrypt/decrypt roundtrips for multi-recipient TOSS v2 blobs."""

import pytest

from toss.crypto.encrypt import DecryptError, decrypt_as_recipient, encrypt_for_recipients
from toss.crypto.keypair import KeyPair


def test_single_recipient_roundtrip() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()

    plaintext = b"the quick brown fox jumps over the lazy dog" * 20
    blob = encrypt_for_recipients(
        plaintext=plaintext,
        filename="note.txt",
        sender=alice,
        recipient_public_keys=[bob.encryption_public_bytes],
    )

    recovered, filename = decrypt_as_recipient(blob, [bob])
    assert recovered == plaintext
    assert filename == "note.txt"


def test_multi_recipient_each_can_decrypt() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()
    carol = KeyPair.generate()
    dave = KeyPair.generate()

    plaintext = b"group message"
    blob = encrypt_for_recipients(
        plaintext,
        "group.md",
        alice,
        [bob.encryption_public_bytes, carol.encryption_public_bytes, dave.encryption_public_bytes],
    )

    for kp in (bob, carol, dave):
        recovered, _ = decrypt_as_recipient(blob, [kp])
        assert recovered == plaintext


def test_non_recipient_cannot_decrypt() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()
    eve = KeyPair.generate()

    blob = encrypt_for_recipients(
        b"secret",
        "s.txt",
        alice,
        [bob.encryption_public_bytes],
    )
    with pytest.raises(DecryptError, match="no matching recipient"):
        decrypt_as_recipient(blob, [eve])


def test_tampered_body_fails_mac() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()
    blob = encrypt_for_recipients(
        b"original payload",
        "x",
        alice,
        [bob.encryption_public_bytes],
    )
    tampered = bytearray(blob)
    tampered[-1] ^= 0x01  # flip last byte of body ciphertext
    with pytest.raises(DecryptError):
        decrypt_as_recipient(bytes(tampered), [bob])


def test_tampered_wrapped_key_fails() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()
    blob = encrypt_for_recipients(b"data", "f", alice, [bob.encryption_public_bytes])
    # wrapped_key sits in the header region; flip a byte ~60 bytes in to hit it
    # without corrupting magic / filename fields.
    idx = len(blob) - 100
    tampered = bytearray(blob)
    tampered[idx] ^= 0xFF
    with pytest.raises(DecryptError):
        decrypt_as_recipient(bytes(tampered), [bob])


def test_rejects_empty_recipient_list() -> None:
    alice = KeyPair.generate()
    with pytest.raises(ValueError, match="at least one recipient"):
        encrypt_for_recipients(b"x", "y", alice, [])


def test_rejects_bad_recipient_key_size() -> None:
    alice = KeyPair.generate()
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_for_recipients(b"x", "y", alice, [b"\x00" * 16])


def test_historical_key_tried_after_current() -> None:
    """Rotated users pass [new_kp, old_kp]; decrypt should succeed on old blob."""
    alice = KeyPair.generate()
    bob_old = KeyPair.generate()
    blob = encrypt_for_recipients(b"legacy", "old.md", alice, [bob_old.encryption_public_bytes])
    bob_new = KeyPair.generate()

    recovered, _ = decrypt_as_recipient(blob, [bob_new, bob_old])
    assert recovered == b"legacy"


def test_expected_sender_pin_enforced() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()
    other_sender = KeyPair.generate()
    blob = encrypt_for_recipients(b"x", "f", alice, [bob.encryption_public_bytes])
    with pytest.raises(DecryptError, match="sender public key"):
        decrypt_as_recipient(
            blob,
            [bob],
            expected_sender_public_key=other_sender.encryption_public_bytes,
        )
    # Correct pin still works
    recovered, _ = decrypt_as_recipient(
        blob,
        [bob],
        expected_sender_public_key=alice.encryption_public_bytes,
    )
    assert recovered == b"x"


def test_filename_unicode_preserved() -> None:
    alice = KeyPair.generate()
    bob = KeyPair.generate()
    blob = encrypt_for_recipients(
        b"hi",
        "中文文件名.md",
        alice,
        [bob.encryption_public_bytes],
    )
    _, filename = decrypt_as_recipient(blob, [bob])
    assert filename == "中文文件名.md"
