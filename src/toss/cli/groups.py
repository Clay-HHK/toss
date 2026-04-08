"""Group CLI subcommands."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from toss.client.base import TossAPIError, TossClient
from toss.client.groups import GroupClient
from toss.config.manager import ConfigManager

console = Console()


def _get_group_client() -> GroupClient:
    client = TossClient.from_config(ConfigManager())
    return GroupClient(client)


def _make_full_invite_code(invite_code: str) -> str:
    """Combine server host with invite code for zero-config joining."""
    cm = ConfigManager()
    config = cm.load_config()
    host = config.server.base_url.replace("https://", "").rstrip("/")
    return f"{host}/{invite_code}"


@click.group()
def group() -> None:
    """Manage groups for multi-person sharing."""


@group.command()
@click.argument("name")
@click.option("--slug", default=None, help="URL-friendly slug (auto-generated if omitted)")
def create(name: str, slug: str | None) -> None:
    """Create a group. Example: toss group create paper-team"""
    try:
        gc = _get_group_client()
        result = gc.create(name, slug)
        full_code = _make_full_invite_code(result.get("invite_code", ""))
        console.print(f"[green]Created[/green] group [bold]{result.get('name')}[/bold]")
        console.print(f"  Slug: {result.get('slug')}")
        console.print(f"  Invite code: [bold cyan]{full_code}[/bold cyan]")
        console.print(
            "\nShare the invite code. Others can join with:\n"
            f"  [bold]toss join {full_code}[/bold]"
        )
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)


@group.command(name="list")
def list_groups() -> None:
    """List groups you belong to."""
    try:
        gc = _get_group_client()
        items = gc.list_groups()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print(
            "[yellow]No groups yet.[/yellow]"
            " Create one with [bold]toss group create[/bold]."
        )
        return

    table = Table(title="My Groups")
    table.add_column("Name", style="bold")
    table.add_column("Slug", style="cyan")
    table.add_column("Members")
    table.add_column("Invite Code")
    for g in items:
        table.add_row(
            g.get("name", ""),
            g.get("slug", ""),
            str(g.get("member_count", "?")),
            g.get("invite_code", ""),
        )
    console.print(table)


@group.command()
@click.argument("slug")
def invite(slug: str) -> None:
    """Show invite code for a group (owner only)."""
    try:
        gc = _get_group_client()
        result = gc.get_invite(slug)
        full_code = _make_full_invite_code(result.get("invite_code", ""))
        console.print(
            f"Group [bold]{result.get('group_name')}[/bold]"
            f" invite code: [bold cyan]{full_code}[/bold cyan]"
        )
        console.print(f"\nJoin command: [bold]toss join {full_code}[/bold]")
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)


@group.command()
@click.argument("invite_code")
def join(invite_code: str) -> None:
    """Join a group with an invite code. Example: toss group join ABCD-1234"""
    try:
        gc = _get_group_client()
        result = gc.join(invite_code)
        console.print(
            f"[green]{result.get('message', 'Joined')}[/green]"
            f" group [bold]{result.get('group_name')}[/bold]"
        )
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)


@group.command()
@click.argument("slug")
def members(slug: str) -> None:
    """List members of a group."""
    try:
        gc = _get_group_client()
        items = gc.list_members(slug)
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print("[yellow]No members.[/yellow]")
        return

    table = Table(title=f"Members of {slug}")
    table.add_column("GitHub", style="bold")
    table.add_column("Name")
    table.add_column("Role")
    for m in items:
        table.add_row(
            f"#{m.get('github_username', '')}",
            m.get("display_name") or "",
            m.get("role", "member"),
        )
    console.print(table)


@group.command(name="push")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.argument("slug")
@click.option("--message", "-m", default=None, help="Attach a message")
def group_push(files: tuple[str, ...], slug: str, message: str | None) -> None:
    """Push files to all group members.

    Example: toss group push report.md paper-team -m "review please"
    """
    try:
        gc = _get_group_client()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    for file_str in files:
        file_path = Path(file_str)
        try:
            result = gc.push(slug, file_path, message)
            console.print(
                f"[green]Pushed[/green] {file_path.name}"
                f" -> group [bold]{result.get('group', slug)}[/bold]"
                f" ({result.get('delivered_count', '?')} members)"
            )
        except TossAPIError as e:
            console.print(f"[red]Failed[/red] {file_path.name}: {e.detail}")
