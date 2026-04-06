"""Document push/pull client."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import TossClient

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
            recipient: Alias or @github_username.
            message: Optional message to attach.

        Returns:
            Server response with document id and status.
        """
        content = file_path.read_bytes()
        content_type = _guess_content_type(file_path.name)

        files = {
            "file": (file_path.name, content, content_type),
        }
        data: dict[str, str] = {"recipient": recipient.lstrip("@")}
        if message:
            data["message"] = message

        return self._client.post_multipart("/api/v1/documents/push", files=files, data=data)

    def list_inbox(self) -> list[dict[str, Any]]:
        """List pending documents in inbox."""
        data = self._client.get("/api/v1/documents/inbox")
        return data.get("documents", [])

    def pull(self, doc_id: str, dest_dir: Path) -> Path:
        """Download a document from inbox.

        Args:
            doc_id: Document ID.
            dest_dir: Directory to save the file.

        Returns:
            Path to the downloaded file.
        """
        resp = self._client.download(f"/api/v1/documents/inbox/{doc_id}/download")

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

        dest_path.write_bytes(resp.content)
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
