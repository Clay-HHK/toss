"""Shared Spaces CLI commands: create, list, add-member, sync, set-default."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from toss.client.base import TossAPIError, TossClient
from toss.client.spaces import SpaceClient
from toss.config.manager import ConfigManager
from toss.sync.engine import SyncEngine

console = Console()


def _get_space_client() -> SpaceClient:
    client = TossClient.from_config(ConfigManager())
    return SpaceClient(client)


@click.group()
def space() -> None:
    """Manage shared spaces."""


@space.command()
@click.argument("name")
@click.option("--slug", default=None, help="URL-safe identifier (auto from name if omitted)")
@click.option("--description", default=None, help="Space description")
def create(name: str, slug: str | None, description: str | None) -> None:
    """Create a new shared space."""
    if slug is None:
        slug = name.lower().replace(" ", "-")

    try:
        sc = _get_space_client()
        result = sc.create(name, slug, description)
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    console.print(f"[green]Created space[/green] [bold]{result.get('slug', slug)}[/bold]")
    console.print(f"  ID: {result.get('id', 'unknown')}")
    if description:
        console.print(f"  Description: {description}")


@space.command("list")
def list_spaces() -> None:
    """List spaces you own or belong to."""
    try:
        sc = _get_space_client()
        spaces = sc.list_spaces()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not spaces:
        console.print("[yellow]No spaces found.[/yellow]")
        console.print("Create one with: [bold]toss space create <name>[/bold]")
        return

    table = Table(title=f"Shared Spaces ({len(spaces)})")
    table.add_column("Slug", style="bold")
    table.add_column("Name")
    table.add_column("Owner")
    table.add_column("Role")
    table.add_column("Created")

    for s in spaces:
        table.add_row(
            s.get("slug", "?"),
            s.get("name", "?"),
            f"#{s.get('owner_username', '?')}",
            s.get("role", "?"),
            s.get("created_at", "")[:10],
        )

    console.print(table)


@space.command("add-member")
@click.argument("slug")
@click.argument("github_username")
def add_member(slug: str, github_username: str) -> None:
    """Add a member to a space (owner only)."""
    try:
        sc = _get_space_client()
        result = sc.add_member(slug, github_username.lstrip("#"))
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    console.print(
        f"[green]Added[/green] @{result.get('member', github_username)}"
        f" to [bold]{result.get('space', slug)}[/bold]"
    )


@space.command()
@click.argument("slug", required=False, default=None)
@click.option(
    "--dir", "directory",
    default=None,
    type=click.Path(),
    help="Local directory to sync (default: ~/.toss/spaces/<slug>)",
)
def sync(slug: str | None, directory: str | None) -> None:
    """Sync files with a shared space."""
    cm = ConfigManager()
    config = cm.load_config()

    if slug is None:
        slug = cm.get_default_space()
        if not slug:
            console.print(
                "[red]Error:[/red] No space specified and no default set.\n"
                "  Specify a slug: [bold]toss space sync <slug>[/bold]\n"
                "  Or set a default: [bold]toss space set-default <slug>[/bold]"
            )
            sys.exit(1)

    if directory is None:
        local_dir = Path(config.spaces_dir).expanduser() / slug
    else:
        local_dir = Path(directory).resolve()

    console.print(f"Syncing [bold]{slug}[/bold] <-> {local_dir}")

    try:
        sc = _get_space_client()
        engine = SyncEngine(sc, config.sync)
        result = engine.sync(slug, local_dir)
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    console.print(
        f"[green]Sync complete.[/green]"
        f" Uploaded: {result.uploaded},"
        f" Downloaded: {result.downloaded},"
        f" Conflicts: {result.conflicts}"
    )

    if result.errors:
        for err in result.errors:
            console.print(f"  [yellow]Warning:[/yellow] {err}")

    if result.conflicts > 0:
        console.print(
            "\n[yellow]Conflicts detected.[/yellow]"
            " Server versions saved as *.server.* files."
            " Resolve manually and re-sync."
        )


@space.command("set-default")
@click.argument("slug")
def set_default(slug: str) -> None:
    """Set the default space for sync commands."""
    cm = ConfigManager()
    cm.set_default_space(slug)
    console.print(f"[green]Default space set to[/green] [bold]{slug}[/bold]")
