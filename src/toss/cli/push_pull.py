"""Push, pull, and inbox CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from toss.client.base import TossAPIError, TossClient
from toss.client.documents import DocumentClient
from toss.config.manager import ConfigManager

console = Console()


def _get_doc_client() -> DocumentClient:
    client = TossClient.from_config(ConfigManager())
    return DocumentClient(client)


@click.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.argument("recipient")
@click.option("--message", "-m", default=None, help="Attach a message")
def push(files: tuple[str, ...], recipient: str, message: str | None) -> None:
    """Push files to a recipient. Last argument is the recipient (alias or @github).

    Examples:
        toss push report.md xiaoming
        toss push data.csv notes.md @zhangsan -m "check this"
    """
    try:
        dc = _get_doc_client()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    for file_str in files:
        file_path = Path(file_str)
        try:
            result = dc.push(file_path, recipient, message)
            console.print(
                f"[green]Pushed[/green] {file_path.name}"
                f" -> [bold]{result.get('recipient', recipient)}[/bold]"
                f" ({_human_size(result.get('size_bytes', 0))})"
            )
        except TossAPIError as e:
            console.print(f"[red]Failed[/red] {file_path.name}: {e.detail}")


@click.command()
@click.option("--to", "dest", default=".", type=click.Path(), help="Download destination directory")
def pull(dest: str) -> None:
    """Pull all pending documents from inbox."""
    try:
        dc = _get_doc_client()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    dest_dir = Path(dest).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        items = dc.list_inbox()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print("[yellow]Inbox empty.[/yellow]")
        return

    console.print(f"Pulling {len(items)} file(s)...")

    for item in items:
        try:
            path = dc.pull(item["id"], dest_dir)
            sender = item.get("sender_username", "unknown")
            console.print(f"  [green]Pulled[/green] {path.name} (from @{sender})")
        except TossAPIError as e:
            console.print(f"  [red]Failed[/red] {item.get('filename', '?')}: {e.detail}")

    console.print(f"[green]Done.[/green] Files saved to {dest_dir}")


@click.command()
def inbox() -> None:
    """List pending documents without downloading."""
    try:
        dc = _get_doc_client()
        items = dc.list_inbox()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print("[yellow]Inbox empty.[/yellow]")
        return

    table = Table(title=f"Inbox ({len(items)} pending)")
    table.add_column("File", style="bold")
    table.add_column("From")
    table.add_column("Size")
    table.add_column("Message")
    table.add_column("Time")

    for item in items:
        table.add_row(
            item.get("filename", "?"),
            f"@{item.get('sender_username', '?')}",
            _human_size(item.get("size_bytes", 0)),
            item.get("message") or "",
            item.get("created_at", "")[:16],
        )

    console.print(table)


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"
