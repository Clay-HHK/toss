"""T1-3: SHA-256 end-to-end verification on documents and spaces clients."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from toss.client.base import TossAPIError, TossClient
from toss.client.documents import DocumentClient
from toss.client.spaces import SpaceClient
from toss.config.models import ServerConfig


@pytest.fixture
def toss_client() -> TossClient:
    client = TossClient(
        ServerConfig(base_url="https://example.test", timeout=5),
        jwt="fake-jwt",
    )
    # Pre-seed an empty feature set so these tests exercise the legacy
    # direct-download path (the ticket flow has its own test file).
    client._features_cache = frozenset()
    return client


@pytest.fixture
def doc_client(toss_client: TossClient) -> DocumentClient:
    return DocumentClient(toss_client)


@pytest.fixture
def space_client(toss_client: TossClient) -> SpaceClient:
    return SpaceClient(toss_client)


def test_push_sends_content_sha256(doc_client: DocumentClient, tmp_path: Path) -> None:
    """Client must compute SHA-256 and send it in the multipart payload."""
    payload = b"hello world"
    expected = hashlib.sha256(payload).hexdigest()

    file_path = tmp_path / "note.md"
    file_path.write_bytes(payload)

    with respx.mock(base_url="https://example.test") as mock:
        route = mock.post("/api/v1/documents/push").mock(
            return_value=httpx.Response(
                201,
                json={"id": "doc-1", "status": "delivered", "content_sha256": expected},
            )
        )

        doc_client.push(file_path, recipient="alice")

        assert route.called
        sent_body = route.calls[0].request.content.decode("latin-1")
        assert "content_sha256" in sent_body
        assert expected in sent_body


def test_pull_verifies_content_sha256(doc_client: DocumentClient, tmp_path: Path) -> None:
    """Matching X-Content-SHA256 header should pass without error."""
    payload = b"authentic bytes"
    expected = hashlib.sha256(payload).hexdigest()

    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/documents/inbox/doc-1/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={
                    "X-Content-SHA256": expected,
                    "Content-Disposition": 'attachment; filename="note.md"',
                },
            )
        )

        dest = doc_client.pull("doc-1", tmp_path)

        assert dest.read_bytes() == payload


def test_pull_rejects_hash_mismatch(doc_client: DocumentClient, tmp_path: Path) -> None:
    """Hash mismatch must raise before any bytes are written to disk."""
    payload = b"tampered bytes"
    wrong_hash = "0" * 64

    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/documents/inbox/doc-2/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={
                    "X-Content-SHA256": wrong_hash,
                    "Content-Disposition": 'attachment; filename="evil.md"',
                },
            )
        )

        with pytest.raises(TossAPIError, match="Content hash mismatch"):
            doc_client.pull("doc-2", tmp_path)

        # Must not have written the tampered file to disk.
        assert list(tmp_path.iterdir()) == []


def test_pull_legacy_server_without_header(
    doc_client: DocumentClient, tmp_path: Path
) -> None:
    """Legacy server without X-Content-SHA256 should still work (fallback path)."""
    payload = b"legacy bytes"

    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/documents/inbox/doc-legacy/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={"Content-Disposition": 'attachment; filename="old.md"'},
            )
        )

        dest = doc_client.pull("doc-legacy", tmp_path)
        assert dest.read_bytes() == payload


def test_space_download_verifies_hash(space_client: SpaceClient, tmp_path: Path) -> None:
    payload = b"space file bytes"
    expected = hashlib.sha256(payload).hexdigest()

    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/spaces/lab/files/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={"X-Content-SHA256": expected},
            )
        )

        dest = space_client.download_file("lab", "notes/day1.md", tmp_path)
        assert dest.read_bytes() == payload


def test_space_download_rejects_hash_mismatch(
    space_client: SpaceClient, tmp_path: Path
) -> None:
    payload = b"tampered space bytes"

    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/spaces/lab/files/download").mock(
            return_value=httpx.Response(
                200,
                content=payload,
                headers={"X-Content-SHA256": "deadbeef" * 8},
            )
        )

        with pytest.raises(TossAPIError, match="Content hash mismatch"):
            space_client.download_file("lab", "notes/day1.md", tmp_path)

        assert not (tmp_path / "notes").exists()
