"""Profile management CLI commands (toss profile ...)."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from toss.config.manager import ConfigManager

console = Console()


@click.group()
def profile() -> None:
    """Manage server profiles (work teams)."""


@profile.command(name="list")
def list_profiles() -> None:
    """List all profiles and show the active one."""
    cm = ConfigManager()
    profiles = cm.list_profiles()

    if not profiles:
        console.print("[yellow]No profiles configured.[/yellow]")
        console.print("Join a team with [bold]toss join <server/CODE>[/bold]")
        console.print("or add one with [bold]toss profile add <name> <url>[/bold]")
        return

    current = cm.current_profile_name
    table = Table(title="Profiles")
    table.add_column("", width=2)
    table.add_column("Name", style="bold cyan")
    table.add_column("Server URL")

    # Load server URLs directly from raw config
    raw = cm._read_yaml(cm._config_path)
    raw = cm._migrate_config_if_needed(raw)
    all_profiles = raw.get("profiles", {})

    for name in profiles:
        marker = "[green]*[/green]" if name == current else ""
        url = all_profiles.get(name, {}).get("server", {}).get("base_url", "")
        table.add_row(marker, name, url)

    console.print(table)
    console.print(f"\nActive: [bold cyan]{current}[/bold cyan]")


@profile.command()
@click.argument("name")
@click.argument("url")
@click.option("--timeout", default=30, show_default=True, help="Request timeout in seconds")
def add(name: str, url: str, timeout: int) -> None:
    """Add a new profile.

    \b
    NAME  Short identifier for this team (e.g. work, lab)
    URL   Toss server base URL (e.g. https://toss-api.example.workers.dev)
    """
    cm = ConfigManager()
    if not cm.is_initialized:
        cm.ensure_dirs()

    if not url.startswith("https://") and not url.startswith("http://"):
        url = f"https://{url}"

    try:
        cm.add_profile(name, url, timeout)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    console.print(f"[green]Added[/green] profile [bold]{name}[/bold] -> {url}")
    console.print(f"Run [bold]toss switch {name}[/bold] to activate it.")


@profile.command()
@click.argument("name")
def remove(name: str) -> None:
    """Remove a profile (cannot remove the active one)."""
    cm = ConfigManager()
    try:
        cm.remove_profile(name)
    except KeyError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    console.print(f"[green]Removed[/green] profile [bold]{name}[/bold]")
