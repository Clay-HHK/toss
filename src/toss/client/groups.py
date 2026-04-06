"""Group management client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import TossAPIError, TossClient


class GroupClient:
    """CRUD operations for groups."""

    def __init__(self, client: TossClient) -> None:
        self._client = client

    def create(self, name: str, slug: str | None = None) -> dict[str, Any]:
        """Create a group. Returns group info with invite_code."""
        payload: dict[str, str] = {"name": name}
        if slug:
            payload["slug"] = slug
        return self._client.post_json("/api/v1/groups", payload)

    def list_groups(self) -> list[dict[str, Any]]:
        """List groups I belong to."""
        data = self._client.get("/api/v1/groups")
        return data.get("groups", [])

    def get_invite(self, slug: str) -> dict[str, Any]:
        """Get invite code for a group (owner only)."""
        return self._client.get(f"/api/v1/groups/{slug}/invite")

    def join(self, invite_code: str) -> dict[str, Any]:
        """Join a group with an invite code."""
        return self._client.post_json("/api/v1/groups/join", {
            "invite_code": invite_code,
        })

    def list_members(self, slug: str) -> list[dict[str, Any]]:
        """List members of a group."""
        data = self._client.get(f"/api/v1/groups/{slug}/members")
        return data.get("members", [])

    def push(
        self,
        slug: str,
        file_path: Path,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Push a file to all group members."""
        max_file_size = 50 * 1024 * 1024
        if file_path.stat().st_size > max_file_size:
            raise TossAPIError(413, "File too large (max 50MB)")

        content = file_path.read_bytes()
        content_type = "application/octet-stream"

        files = {"file": (file_path.name, content, content_type)}
        data: dict[str, str] = {}
        if message:
            data["message"] = message

        return self._client.post_multipart(
            f"/api/v1/groups/{slug}/push",
            files=files,
            data=data,
        )
