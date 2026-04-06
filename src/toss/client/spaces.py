"""Shared Spaces client for create, list, add member, sync, upload, download."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import TossClient

logger = logging.getLogger(__name__)


class SpaceClient:
    """Interact with the Toss Shared Spaces API."""

    def __init__(self, client: TossClient) -> None:
        self._client = client

    def create(
        self,
        name: str,
        slug: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new shared space.

        Args:
            name: Display name for the space.
            slug: URL-safe identifier (lowercase, hyphens).
            description: Optional description.

        Returns:
            Server response with space id, name, slug.
        """
        payload: dict[str, Any] = {"name": name, "slug": slug}
        if description:
            payload["description"] = description
        return self._client.post_json("/api/v1/spaces", payload)

    def list_spaces(self) -> list[dict[str, Any]]:
        """List spaces the current user owns or is a member of."""
        data = self._client.get("/api/v1/spaces")
        return data.get("spaces", [])

    def add_member(self, slug: str, github_username: str) -> dict[str, Any]:
        """Add a member to a space (owner only).

        Args:
            slug: Space slug.
            github_username: GitHub username of the user to add.

        Returns:
            Server response confirming membership.
        """
        return self._client.post_json(
            f"/api/v1/spaces/{slug}/members",
            {"github_username": github_username},
        )

    def sync(self, slug: str, manifest: list[dict[str, Any]]) -> dict[str, Any]:
        """Send local manifest and get sync diff from server.

        Args:
            slug: Space slug.
            manifest: List of {path, content_hash} entries.

        Returns:
            Dict with to_download, to_upload, conflicts lists.
        """
        return self._client.post_json(
            f"/api/v1/spaces/{slug}/sync",
            {"manifest": manifest},
        )

    def upload_file(self, slug: str, path: str, file_path: Path) -> dict[str, Any]:
        """Upload a single file to a shared space.

        Args:
            slug: Space slug.
            path: Relative path within the space (POSIX style).
            file_path: Local file to upload.

        Returns:
            Server response with path, content_hash, size_bytes, version.
        """
        content = file_path.read_bytes()
        content_type = "application/octet-stream"
        filename = file_path.name

        files = {"file": (filename, content, content_type)}
        data = {"path": path}

        return self._client.post_multipart(
            f"/api/v1/spaces/{slug}/files/upload",
            files=files,
            data=data,
        )

    def download_file(self, slug: str, path: str, dest_dir: Path) -> Path:
        """Download a single file from a shared space.

        Args:
            slug: Space slug.
            path: Relative path within the space.
            dest_dir: Local directory to save the file into.

        Returns:
            Path to the downloaded file.
        """
        resp = self._client.download(
            f"/api/v1/spaces/{slug}/files/download",
            params={"path": path},
        )

        # Reconstruct local path from the space-relative path
        dest_path = dest_dir / path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(resp.content)
        logger.info("Downloaded %s -> %s", path, dest_path)
        return dest_path
