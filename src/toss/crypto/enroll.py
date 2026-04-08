"""Post-login enrollment hook.

Called once per login to:

1. Load (or lazily generate) the user's local keypair via the configured
   :class:`KeyStore`.
2. Check whether the server already has a matching public key on file.
3. If not, build a canonical proof of possession signed with the Ed25519
   private key and POST both public keys to ``/api/v1/keys``.

Enrollment is **opt-in** in Phase A:

- If the server does not advertise ``pubkey-directory`` via ``/health``
  features, this is a silent no-op.
- If the server is reachable but enrollment fails for any other reason, the
  failure is returned to the caller so the CLI can show a warning — it
  **does not** abort login, because a healthy login still works without a
  published key in Phase A.

Canonical proof message (must match worker/src/handlers/keys.ts):

::

    toss-enroll-v1
    <github_username>
    <x25519_pubkey_b64url>
    <issued_at>
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .keypair import ENCRYPT_PREFIX, _b64u_encode, KeyPair
from .keystore import KeyStore, KeyStoreError

logger = logging.getLogger(__name__)

FEATURE_FLAG = "pubkey-directory"


@dataclass(frozen=True)
class EnrollResult:
    keypair: KeyPair
    new_enrollment: bool  # True if we just uploaded, False if already matched
    skipped_reason: str | None = None  # e.g. "server lacks pubkey-directory"


class EnrollError(Exception):
    """Raised on any unrecoverable enrollment failure."""


def _canonical_proof_message(
    github_username: str,
    x25519_pub_b64u: str,
    issued_at: int,
) -> bytes:
    return (
        f"toss-enroll-v1\n{github_username}\n{x25519_pub_b64u}\n{issued_at}"
    ).encode("utf-8")


def build_enrollment_payload(
    github_username: str,
    keypair: KeyPair,
    issued_at: int | None = None,
) -> dict[str, object]:
    """Assemble a signed enrollment request body.

    Exposed as a standalone function for unit testing without an HTTP client.
    """
    if issued_at is None:
        issued_at = int(time.time())

    x25519_pub_b64u = _b64u_encode(keypair.encryption_public_bytes)
    message = _canonical_proof_message(github_username, x25519_pub_b64u, issued_at)
    proof_sig = keypair.sign(message)

    return {
        "public_key": keypair.encryption_public_str(),
        "signing_public_key": keypair.signing_public_str(),
        "proof": _b64u_encode(proof_sig),
        "issued_at": issued_at,
    }


def ensure_enrolled(
    api_base_url: str,
    jwt: str,
    github_username: str,
    keystore: KeyStore,
    *,
    server_features: frozenset[str] | None = None,
    timeout: float = 10.0,
    http_client: httpx.Client | None = None,
) -> EnrollResult:
    """Idempotently ensure the caller has a published keypair.

    :param api_base_url: Worker base URL, e.g. ``https://api.toss.example``
    :param jwt: Authenticated bearer token for the caller
    :param github_username: The caller's GitHub username (from login result)
    :param keystore: Where to load/save the local keypair
    :param server_features: Optional pre-fetched feature set. If given, this
        function will not call ``/health`` itself — useful when the caller
        already warmed the client cache.
    :param timeout: Per-request timeout in seconds
    :param http_client: Optional pre-built client (for tests/respx)

    :returns: :class:`EnrollResult` with the loaded keypair
    :raises EnrollError: on unrecoverable failure (malformed server response,
        keystore write failure, proof rejected)
    """
    if server_features is not None and FEATURE_FLAG not in server_features:
        kp = _load_or_create(keystore)
        return EnrollResult(
            keypair=kp,
            new_enrollment=False,
            skipped_reason=f"server does not advertise {FEATURE_FLAG}",
        )

    kp = _load_or_create(keystore)

    owns_client = http_client is None
    client = http_client or httpx.Client(
        base_url=api_base_url.rstrip("/"),
        timeout=timeout,
        headers={"Authorization": f"Bearer {jwt}"},
    )
    try:
        existing = _fetch_current_key(client, github_username)
        if existing and existing.get("public_key") == kp.encryption_public_str():
            return EnrollResult(keypair=kp, new_enrollment=False)

        payload = build_enrollment_payload(github_username, kp)
        resp = client.post("/api/v1/keys", json=payload)
        if resp.status_code >= 400:
            detail: object
            try:
                detail = resp.json().get("error", resp.text)
            except Exception:
                detail = resp.text
            raise EnrollError(f"Enrollment failed ({resp.status_code}): {detail}")
    finally:
        if owns_client:
            client.close()

    return EnrollResult(keypair=kp, new_enrollment=True)


def _load_or_create(keystore: KeyStore) -> KeyPair:
    try:
        existing = keystore.load()
    except KeyStoreError as e:
        raise EnrollError(f"Could not load keystore: {e}") from e
    if existing is not None:
        return existing

    fresh = KeyPair.generate()
    try:
        keystore.save(fresh)
    except KeyStoreError as e:
        raise EnrollError(f"Could not persist new keypair: {e}") from e
    logger.info(
        "Generated new local keypair (fingerprint=%s); save a backup with `toss keys export`",
        fresh.fingerprint(),
    )
    return fresh


def _fetch_current_key(
    client: httpx.Client,
    github_username: str,
) -> dict[str, object] | None:
    resp = client.get(f"/api/v1/keys/{github_username}")
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise EnrollError(f"Unexpected status fetching current key: {resp.status_code}")
    try:
        data = resp.json()
    except ValueError as e:
        raise EnrollError(f"Invalid JSON from /api/v1/keys/{github_username}: {e}") from e
    if not isinstance(data, dict):
        raise EnrollError(f"Expected object from /api/v1/keys/{github_username}")
    return data
