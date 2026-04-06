"""Contact management client."""

from __future__ import annotations

from typing import Any

from .base import TossClient


class ContactClient:
    """CRUD operations for contacts (aliases)."""

    def __init__(self, client: TossClient) -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        """List all contacts."""
        data = self._client.get("/api/v1/contacts")
        return data.get("contacts", [])

    def add(self, github_username: str, alias: str) -> dict[str, Any]:
        """Add a contact with an alias."""
        return self._client.post_json("/api/v1/contacts", {
            "github_username": github_username,
            "alias": alias,
        })

    def remove(self, alias: str) -> dict[str, Any]:
        """Remove a contact by alias."""
        return self._client.delete(f"/api/v1/contacts/{alias}")

    def resolve(self, alias_or_username: str) -> dict[str, Any]:
        """Resolve an alias or @username to a user."""
        name = alias_or_username.lstrip("@")
        return self._client.get(f"/api/v1/contacts/resolve/{name}")
