"""T1-2: client-side two-phase download ticket flow."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from toss.client.base import TossClient
from toss.client.documents import DocumentClient
from toss.client.spaces import SpaceClient
from toss.config.models import ServerConfig


def _make_client() -> TossClient:
    return TossClient(
        ServerConfig(base_url="https://example.test", timeout=5),
        jwt="fake-jwt",
    )


def _prime_feature(mock: respx.MockRouter, *, enabled: bool) -> None:
    features = ["content-sha256", "download-ticket"] if enabled else ["content-sha256"]
    mock.get("/api/v1/health").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "version": "0.2.0", "features": features}
        )
    )


def test_pull_uses_ticket_when_feature_advertised(tmp_path: Path) -> None:
    payload = b"ticketed bytes"
    expected_hash = hashlib.sha256(payload).hexdigest()

    client = _make_client()
    doc_client = DocumentClient(client)

    with respx.mock(base_url="https://example.test") as mock:
        _prime_feature(mock, enabled=True)
        mint = mock.post("/api/v1/documents/inbox/doc-42/ticket").mock(
            return_value=httpx.Response(
                200, json={"url": "/api/v1/blobs/TOKEN", "expires_in": 300}
            )
        )
        redeem = mock.get("/api/v1/blobs/TOKEN").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={
                    "X-Content-SHA256": expected_hash,
                    "Content-Disposition": 'attachment; filename="note.md"',
                },
            )
        )

        dest = doc_client.pull("doc-42", tmp_path)

    assert mint.called
    assert redeem.called
    assert dest.read_bytes() == payload


def test_pull_falls_back_to_legacy_when_feature_missing(tmp_path: Path) -> None:
    payload = b"legacy bytes"

    client = _make_client()
    doc_client = DocumentClient(client)

    with respx.mock(base_url="https://example.test") as mock:
        _prime_feature(mock, enabled=False)
        legacy = mock.get("/api/v1/documents/inbox/doc-7/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={"Content-Disposition": 'attachment; filename="old.md"'},
            )
        )

        dest = doc_client.pull("doc-7", tmp_path)

    assert legacy.called
    assert dest.read_bytes() == payload


def test_pull_falls_back_when_ticket_mint_fails(tmp_path: Path) -> None:
    """If ticket mint 5xxs, client must still try the legacy path instead of crashing."""
    payload = b"resilient bytes"

    client = _make_client()
    doc_client = DocumentClient(client)

    with respx.mock(base_url="https://example.test") as mock:
        _prime_feature(mock, enabled=True)
        mock.post("/api/v1/documents/inbox/doc-x/ticket").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        legacy = mock.get("/api/v1/documents/inbox/doc-x/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={"Content-Disposition": 'attachment; filename="x.md"'},
            )
        )

        dest = doc_client.pull("doc-x", tmp_path)

    assert legacy.called
    assert dest.read_bytes() == payload


def test_space_download_uses_ticket(tmp_path: Path) -> None:
    payload = b"space ticketed bytes"
    expected_hash = hashlib.sha256(payload).hexdigest()

    client = _make_client()
    space_client = SpaceClient(client)

    with respx.mock(base_url="https://example.test") as mock:
        _prime_feature(mock, enabled=True)
        mint = mock.post("/api/v1/spaces/lab/files/ticket").mock(
            return_value=httpx.Response(
                200, json={"url": "/api/v1/blobs/S-TOKEN", "expires_in": 300}
            )
        )
        redeem = mock.get("/api/v1/blobs/S-TOKEN").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={"X-Content-SHA256": expected_hash},
            )
        )

        dest = space_client.download_file("lab", "notes/day1.md", tmp_path)

    assert mint.called
    assert "path=notes" in str(mint.calls[0].request.url)
    assert redeem.called
    assert dest.read_bytes() == payload


def test_space_download_falls_back_to_legacy(tmp_path: Path) -> None:
    payload = b"legacy space bytes"

    client = _make_client()
    space_client = SpaceClient(client)

    with respx.mock(base_url="https://example.test") as mock:
        _prime_feature(mock, enabled=False)
        legacy = mock.get("/api/v1/spaces/lab/files/download").mock(
            return_value=httpx.Response(200, content=payload)
        )

        dest = space_client.download_file("lab", "notes/day1.md", tmp_path)

    assert legacy.called
    assert dest.read_bytes() == payload
