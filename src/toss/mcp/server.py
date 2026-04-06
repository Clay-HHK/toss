"""Toss MCP server for Claude Code / Cursor integration."""

from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from toss.client.base import TossAPIError, TossClient
from toss.client.contacts import ContactClient
from toss.client.documents import DocumentClient
from toss.config.manager import ConfigManager

logger = logging.getLogger(__name__)

mcp = FastMCP("toss", instructions="Toss: share documents between AI agent users")


def _make_document_client() -> DocumentClient:
    """Create a DocumentClient from stored config."""
    client = TossClient.from_config(ConfigManager())
    return DocumentClient(client)


def _make_contact_client() -> ContactClient:
    """Create a ContactClient from stored config."""
    client = TossClient.from_config(ConfigManager())
    return ContactClient(client)


@mcp.tool()
def push_document(
    file_path: str,
    recipient: str,
    message: str | None = None,
) -> str:
    """Push a document to a recipient.

    Args:
        file_path: Path to the local file to send.
        recipient: Alias or @github_username of the recipient.
        message: Optional message to attach.

    Returns:
        Success or error message.
    """
    try:
        dc = _make_document_client()
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            return f"Error: file not found: {file_path}"
        dc.push(path, recipient, message)
        return f"Pushed {path.name} to {recipient}"
    except TossAPIError as e:
        return f"Error: {e.detail}"


@mcp.tool()
def pull_documents(dest_dir: str = ".") -> str:
    """Pull all pending documents from inbox.

    Args:
        dest_dir: Directory to save downloaded files. Defaults to current directory.

    Returns:
        Summary of pulled files or error message.
    """
    try:
        dc = _make_document_client()
        dest = Path(dest_dir).expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)
        items = dc.list_inbox()
        if not items:
            return "Inbox is empty, nothing to pull."
        downloaded: list[Path] = []
        for item in items:
            path = dc.pull(item["id"], dest)
            downloaded.append(path)
        names = ", ".join(p.name for p in downloaded)
        return f"Pulled {len(downloaded)} file(s): {names}"
    except TossAPIError as e:
        return f"Error: {e.detail}"


@mcp.tool()
def list_inbox() -> str:
    """List pending documents in your Toss inbox.

    Returns:
        Plain text table of inbox items or error message.
    """
    try:
        dc = _make_document_client()
        items = dc.list_inbox()
        if not items:
            return "Inbox is empty."
        lines = [_format_inbox_header()]
        for item in items:
            lines.append(_format_inbox_row(item))
        return "\n".join(lines)
    except TossAPIError as e:
        return f"Error: {e.detail}"


@mcp.tool()
def list_contacts() -> str:
    """List your Toss contacts.

    Returns:
        Plain text list of contacts or error message.
    """
    try:
        cc = _make_contact_client()
        contacts = cc.list()
        if not contacts:
            return "No contacts."
        lines = ["Alias            GitHub Username"]
        lines.append("-" * 40)
        for c in contacts:
            alias = c.get("alias", "")
            gh = c.get("github_username", "")
            lines.append(f"{alias:<16} {gh}")
        return "\n".join(lines)
    except TossAPIError as e:
        return f"Error: {e.detail}"


@mcp.tool()
def add_contact(github_username: str, alias: str) -> str:
    """Add a contact.

    Args:
        github_username: GitHub username to add.
        alias: Short alias for this contact.

    Returns:
        Confirmation or error message.
    """
    try:
        cc = _make_contact_client()
        cc.add(github_username, alias)
        return f"Added contact: {alias} -> @{github_username}"
    except TossAPIError as e:
        return f"Error: {e.detail}"


@mcp.tool()
def remove_contact(alias: str) -> str:
    """Remove a contact by alias.

    Args:
        alias: Alias of the contact to remove.

    Returns:
        Confirmation or error message.
    """
    try:
        cc = _make_contact_client()
        cc.remove(alias)
        return f"Removed contact: {alias}"
    except TossAPIError as e:
        return f"Error: {e.detail}"


# -- Formatting helpers -------------------------------------------------------


def _format_inbox_header() -> str:
    return (
        f"{'Filename':<30} {'From':<16} {'Size':<10} {'Message':<20} {'Time'}"
    )


def _format_inbox_row(item: dict) -> str:
    filename = item.get("filename", "?")[:29]
    sender = item.get("sender", "?")[:15]
    size = _human_size(item.get("size", 0))
    message = (item.get("message") or "")[:19]
    time = item.get("created_at", "?")[:19]
    return f"{filename:<30} {sender:<16} {size:<10} {message:<20} {time}"


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.0f}{unit}" if unit == "B" else f"{nbytes:.1f}{unit}"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f}TB"


if __name__ == "__main__":
    mcp.run()
