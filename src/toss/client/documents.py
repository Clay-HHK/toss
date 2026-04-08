"""Document push/pull client."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from .base import TossAPIError, TossClient

logger = logging.getLogger(__name__)


class DocumentClient:
    """Push and pull documents through the Toss API."""

    def __init__(self, client: TossClient) -> None:
        self._client = client

    def push(
        self,
        file_path: Path,
        recipient: str,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Push a file to a recipient.

        Args:
            file_path: Local file to push.
            recipient: Alias or #github_username.
            message: Optional message to attach.

        Returns:
            Server response with document id and status.
        """
        max_file_size = 50 * 1024 * 1024  # 50MB
        if file_path.stat().st_size > max_file_size:
            raise TossAPIError(413, "File too large (max 50MB)")

        content = file_path.read_bytes()
        content_type = _guess_content_type(file_path.name)

        # T1-3: compute SHA-256 on the client so the server can verify the
        # upload round-trip and the recipient can verify the download.
        content_sha256 = hashlib.sha256(content).hexdigest()

        files = {
            "file": (file_path.name, content, content_type),
        }
        data: dict[str, str] = {
            "recipient": recipient.lstrip("#"),
            "content_sha256": content_sha256,
        }
        if message:
            data["message"] = message

        return self._client.post_multipart("/api/v1/documents/push", files=files, data=data)

    def list_inbox(self) -> list[dict[str, Any]]:
        """List pending documents in inbox."""
        data = self._client.get("/api/v1/documents/inbox")
        return data.get("documents", [])

    def preview(self, doc_id: str) -> dict[str, Any]:
        """Fetch a preview of a document without marking it as pulled."""
        return self._client.get(f"/api/v1/documents/inbox/{doc_id}/preview")

    def delete(self, doc_id: str) -> dict[str, Any]:
        """Delete a document from inbox without pulling."""
        return self._client.delete(f"/api/v1/documents/inbox/{doc_id}")

    def pull(self, doc_id: str, dest_dir: Path) -> Path:
        """Download a document from inbox.

        Args:
            doc_id: Document ID.
            dest_dir: Directory to save the file.

        Returns:
            Path to the downloaded file.

        Raises:
            TossAPIError: If the server-supplied SHA-256 header does not match
                the downloaded bytes (integrity failure).
        """
        # T1-2: prefer the two-phase ticket flow when the server advertises
        # `download-ticket`. Fall back to the legacy direct-download route so
        # this client still works against pre-T1-2 deployments.
        if self._client.has_feature("download-ticket"):
            try:
                ticket_resp = self._client.post_json(
                    f"/api/v1/documents/inbox/{doc_id}/ticket",
                    {},
                )
                ticket_url = ticket_resp["url"]
                resp = self._client.download(ticket_url)
            except (TossAPIError, KeyError) as e:
                logger.debug("Ticket mint failed (%s); falling back to /download", e)
                resp = self._client.download(f"/api/v1/documents/inbox/{doc_id}/download")
        else:
            resp = self._client.download(f"/api/v1/documents/inbox/{doc_id}/download")

        # T1-3: verify integrity against server-supplied SHA-256 before writing.
        # Older servers omit the header; in that case we fall back silently.
        expected = resp.headers.get("X-Content-SHA256")
        content = resp.content
        if expected:
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected.lower():
                raise TossAPIError(
                    0,
                    f"Content hash mismatch for document {doc_id}: "
                    f"expected {expected}, got {actual}",
                )
        else:
            logger.debug("No X-Content-SHA256 header for %s, skipping verification", doc_id)

        filename = _extract_filename(resp) or f"{doc_id}.bin"
        dest_path = dest_dir / filename

        # Avoid overwriting
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        dest_path.write_bytes(content)
        return dest_path

    def pull_all(self, dest_dir: Path) -> list[Path]:
        """Pull all pending documents from inbox."""
        items = self.list_inbox()
        downloaded: list[Path] = []
        for item in items:
            path = self.pull(item["id"], dest_dir)
            downloaded.append(path)
        return downloaded

    def list_sent(self) -> list[dict[str, Any]]:
        """List documents I have sent."""
        data = self._client.get("/api/v1/documents/sent")
        return data.get("documents", [])


def _guess_content_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    types: dict[str, str] = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".py": "text/x-python",
        ".ts": "text/typescript",
        ".js": "text/javascript",
        ".html": "text/html",
        ".css": "text/css",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".zip": "application/zip",
    }
    return types.get(ext, "application/octet-stream")


def _extract_filename(resp: Any) -> str | None:
    cd = resp.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        parts = cd.split("filename=")
        if len(parts) > 1:
            return parts[1].strip().strip('"')
    return None
