"""Tests for toss.crypto.keypair."""

import pytest

from toss.crypto.keypair import (
    ENCRYPT_PREFIX,
    SEED_SIZE,
    SIGNING_PREFIX,
    KeyPair,
    fingerprint_from_public_key,
    parse_encryption_public_key,
    parse_signing_public_key,
)


def test_generate_yields_unique_keys() -> None:
    a = KeyPair.generate()
    b = KeyPair.generate()
    assert a.seed != b.seed
    assert a.encryption_public_bytes != b.encryption_public_bytes
    assert a.signing_public_bytes != b.signing_public_bytes


def test_seed_round_trip() -> None:
    kp = KeyPair.generate()
    as_text = kp.seed_b64()
    restored = KeyPair.from_seed_b64(as_text)
    assert restored.seed == kp.seed
    assert restored.encryption_public_bytes == kp.encryption_public_bytes


def test_seed_wrong_size_rejected() -> None:
    with pytest.raises(ValueError, match="seed must be"):
        KeyPair(seed=b"\x00" * (SEED_SIZE - 1))


def test_public_key_encoding_prefixes() -> None:
    kp = KeyPair.generate()
    assert kp.encryption_public_str().startswith(ENCRYPT_PREFIX)
    assert kp.signing_public_str().startswith(SIGNING_PREFIX)


def test_public_key_encoding_round_trip() -> None:
    kp = KeyPair.generate()
    enc_decoded = parse_encryption_public_key(kp.encryption_public_str())
    sig_decoded = parse_signing_public_key(kp.signing_public_str())
    assert enc_decoded == kp.encryption_public_bytes
    assert sig_decoded == kp.signing_public_bytes


def test_parse_rejects_wrong_prefix() -> None:
    kp = KeyPair.generate()
    with pytest.raises(ValueError, match="prefix"):
        parse_encryption_public_key(kp.signing_public_str())
    with pytest.raises(ValueError, match="prefix"):
        parse_signing_public_key(kp.encryption_public_str())


def test_fingerprint_is_stable_and_formatted() -> None:
    kp = KeyPair.generate()
    fp = kp.fingerprint()
    assert fp == fingerprint_from_public_key(kp.encryption_public_bytes)
    # Format is 8 bytes colon-separated hex: "aa:bb:cc:dd:ee:ff:gg:hh"
    parts = fp.split(":")
    assert len(parts) == 8
    assert all(len(p) == 2 for p in parts)


def test_sign_produces_verifiable_signature() -> None:
    kp = KeyPair.generate()
    msg = b"hello toss"
    sig = kp.sign(msg)
    # Signature is 64 bytes for Ed25519
    assert len(sig) == 64
    kp.verify_key.verify(msg, sig)
