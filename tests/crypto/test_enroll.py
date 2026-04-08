"""Tests for toss.crypto.enroll.

The enrollment flow talks to the Worker via HTTPS, so we stub the Worker with
respx. The crypto primitives themselves are covered by test_keypair /
test_header / test_encrypt — these tests focus on the HTTP protocol
contract and the skip / error paths.
"""

import base64
from pathlib import Path

import httpx
import pytest
import respx
from nacl.signing import VerifyKey

from toss.crypto.enroll import (
    EnrollError,
    build_enrollment_payload,
    ensure_enrolled,
)
from toss.crypto.keypair import (
    KeyPair,
    parse_encryption_public_key,
    parse_signing_public_key,
)
from toss.crypto.keystore import FileKeyStore


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _verify_proof(payload: dict[str, object], github_username: str) -> None:
    """Recompute the canonical message and verify the Ed25519 proof."""
    pub_x = payload["public_key"]
    assert isinstance(pub_x, str)
    # x25519 portion without the toss1 prefix
    x25519_b64u = pub_x.removeprefix("toss1")
    message = (
        f"toss-enroll-v1\n{github_username}\n{x25519_b64u}\n{payload['issued_at']}"
    ).encode("utf-8")
    signing_pub_bytes = parse_signing_public_key(str(payload["signing_public_key"]))
    proof_bytes = _b64u_decode(str(payload["proof"]))
    VerifyKey(signing_pub_bytes).verify(message, proof_bytes)


def test_build_payload_proof_is_valid() -> None:
    kp = KeyPair.generate()
    payload = build_enrollment_payload("alice", kp, issued_at=1_700_000_000)
    assert payload["issued_at"] == 1_700_000_000
    assert payload["public_key"].startswith("toss1")  # type: ignore[union-attr]
    assert payload["signing_public_key"].startswith("tossk1")  # type: ignore[union-attr]
    _verify_proof(payload, "alice")


def test_build_payload_public_key_matches_encoded_bytes() -> None:
    kp = KeyPair.generate()
    payload = build_enrollment_payload("bob", kp)
    decoded = parse_encryption_public_key(str(payload["public_key"]))
    assert decoded == kp.encryption_public_bytes


@respx.mock
def test_enroll_fresh_uploads_and_persists(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "k.seed")
    assert not store.exists()

    get_route = respx.get("https://toss.example/api/v1/keys/alice").mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "alice",
                "public_key": None,
                "signing_public_key": None,
                "proof": None,
                "issued_at": None,
                "updated_at": None,
            },
        ),
    )
    post_route = respx.post("https://toss.example/api/v1/keys").mock(
        return_value=httpx.Response(201, json={"ok": True}),
    )

    result = ensure_enrolled(
        api_base_url="https://toss.example",
        jwt="jwt-token",
        github_username="alice",
        keystore=store,
    )
    assert result.new_enrollment is True
    assert result.skipped_reason is None
    assert store.exists()
    assert get_route.called
    assert post_route.called

    # Verify the POST body carried a well-formed, signature-valid payload.
    body = post_route.calls.last.request.content
    import json as _json

    payload = _json.loads(body)
    _verify_proof(payload, "alice")


@respx.mock
def test_enroll_skips_upload_when_already_matches(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "k.seed")
    existing = KeyPair.generate()
    store.save(existing)

    respx.get("https://toss.example/api/v1/keys/bob").mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "bob",
                "public_key": existing.encryption_public_str(),
                "signing_public_key": existing.signing_public_str(),
                "proof": "whatever",
                "issued_at": 1_700_000_000,
                "updated_at": "2025-01-01T00:00:00Z",
            },
        ),
    )
    post_route = respx.post("https://toss.example/api/v1/keys").mock(
        return_value=httpx.Response(500),
    )

    result = ensure_enrolled(
        api_base_url="https://toss.example",
        jwt="jwt",
        github_username="bob",
        keystore=store,
    )
    assert result.new_enrollment is False
    assert result.skipped_reason is None
    assert not post_route.called


@respx.mock
def test_enroll_reuploads_when_server_key_mismatches(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "k.seed")
    local_kp = KeyPair.generate()
    store.save(local_kp)
    stale_server_kp = KeyPair.generate()

    respx.get("https://toss.example/api/v1/keys/carol").mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "carol",
                "public_key": stale_server_kp.encryption_public_str(),
                "signing_public_key": stale_server_kp.signing_public_str(),
                "proof": "old",
                "issued_at": 1_600_000_000,
                "updated_at": "2023-01-01T00:00:00Z",
            },
        ),
    )
    post_route = respx.post("https://toss.example/api/v1/keys").mock(
        return_value=httpx.Response(201, json={"ok": True}),
    )

    result = ensure_enrolled(
        api_base_url="https://toss.example",
        jwt="jwt",
        github_username="carol",
        keystore=store,
    )
    assert result.new_enrollment is True
    assert post_route.called


@respx.mock
def test_enroll_handles_404_as_unknown_user(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "k.seed")
    respx.get("https://toss.example/api/v1/keys/dave").mock(
        return_value=httpx.Response(404, json={"error": "User not found"}),
    )
    post_route = respx.post("https://toss.example/api/v1/keys").mock(
        return_value=httpx.Response(201, json={"ok": True}),
    )

    result = ensure_enrolled(
        api_base_url="https://toss.example",
        jwt="jwt",
        github_username="dave",
        keystore=store,
    )
    assert result.new_enrollment is True
    assert post_route.called


def test_enroll_skips_when_feature_absent(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "k.seed")
    result = ensure_enrolled(
        api_base_url="https://toss.example",
        jwt="jwt",
        github_username="eve",
        keystore=store,
        server_features=frozenset({"content-sha256"}),
    )
    assert result.new_enrollment is False
    assert result.skipped_reason is not None
    assert "pubkey-directory" in result.skipped_reason
    # Still created + persisted a local keypair (so subsequent encrypt works).
    assert store.exists()


@respx.mock
def test_enroll_raises_on_server_rejection(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "k.seed")
    respx.get("https://toss.example/api/v1/keys/frank").mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "frank",
                "public_key": None,
                "signing_public_key": None,
                "proof": None,
                "issued_at": None,
                "updated_at": None,
            },
        ),
    )
    respx.post("https://toss.example/api/v1/keys").mock(
        return_value=httpx.Response(400, json={"error": "proof signature did not verify"}),
    )
    with pytest.raises(EnrollError, match="proof signature"):
        ensure_enrolled(
            api_base_url="https://toss.example",
            jwt="jwt",
            github_username="frank",
            keystore=store,
        )
