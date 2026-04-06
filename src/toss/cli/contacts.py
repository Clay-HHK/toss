"""Contacts CLI subcommands."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from toss.client.base import TossAPIError, TossClient
from toss.client.contacts import ContactClient
from toss.config.manager import ConfigManager

console = Console()


@click.group()
def contacts() -> None:
    """Manage contacts (aliases for collaborators)."""


@contacts.command()
@click.argument("github_username")
@click.option("--alias", "-a", required=True, help="Local alias for this contact")
def add(github_username: str, alias: str) -> None:
    """Add a contact. Example: toss contacts add zhangsan --alias xiaoming"""
    try:
        client = TossClient.from_config(ConfigManager())
        cc = ContactClient(client)
        result = cc.add(github_username, alias)
        console.print(
            f"[green]Added[/green] {result.get('github_username', github_username)}"
            f" as [bold]{alias}[/bold]"
        )
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)


@contacts.command(name="list")
def list_contacts() -> None:
    """List all contacts."""
    try:
        client = TossClient.from_config(ConfigManager())
        cc = ContactClient(client)
        items = cc.list()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print("[yellow]No contacts yet.[/yellow] Add one with [bold]toss contacts add[/bold].")
        return

    table = Table(title="Contacts")
    table.add_column("Alias", style="bold cyan")
    table.add_column("GitHub")
    for c in items:
        table.add_row(c.get("alias", ""), c.get("github_username", ""))
    console.print(table)


@contacts.command()
@click.argument("alias")
def remove(alias: str) -> None:
    """Remove a contact by alias."""
    try:
        client = TossClient.from_config(ConfigManager())
        cc = ContactClient(client)
        cc.remove(alias)
        console.print(f"[green]Removed[/green] contact [bold]{alias}[/bold]")
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)
