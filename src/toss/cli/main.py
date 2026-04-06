"""Toss CLI entry point: init, login, whoami commands."""

from __future__ import annotations

import getpass
import sys

import click
from rich.console import Console

from toss.auth.github import AuthError, GitHubAuth
from toss.auth.token_store import TokenStore
from toss.cli.contacts import contacts
from toss.cli.push_pull import inbox, pull, push
from toss.config.manager import ConfigManager

console = Console()


def _get_config_manager() -> ConfigManager:
    return ConfigManager()


@click.group(invoke_without_command=True)
@click.version_option(package_name="toss")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Toss: Agent-to-Agent document sharing tool."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Register subcommands
main.add_command(contacts)
main.add_command(push)
main.add_command(pull)
main.add_command(inbox)


@main.command()
def init() -> None:
    """Initialize Toss configuration directory (~/.toss/)."""
    cm = _get_config_manager()

    if cm.is_initialized:
        console.print("[yellow]Already initialized.[/yellow]", f"Config dir: {cm.base_dir}")
        return

    cm.ensure_dirs()
    config = cm.load_config()
    cm.save_config(config)
    console.print("[green]Initialized![/green]", f"Config dir: {cm.base_dir}")
    console.print(
        "\n[bold]Next steps:[/bold]\n"
        "  1. Edit [cyan]~/.toss/config.yaml[/cyan] and set [bold]base_url[/bold]"
        " to your team's Worker URL\n"
        "  2. Run [bold]toss login --pat[/bold] to authenticate with GitHub"
    )


@main.command()
@click.option("--pat", is_flag=True, help="Authenticate with a GitHub Personal Access Token")
def login(pat: bool) -> None:
    """Authenticate with GitHub."""
    cm = _get_config_manager()
    if not cm.is_initialized:
        console.print("[red]Not initialized.[/red] Run [bold]toss init[/bold] first.")
        sys.exit(1)

    config = cm.load_config()
    auth = GitHubAuth(config.server.base_url, config.server.timeout)
    store = TokenStore(cm)

    if pat:
        _login_pat(auth, store)
    else:
        _login_device_flow(auth, store)


def _login_pat(auth: GitHubAuth, store: TokenStore) -> None:
    """Login with GitHub PAT."""
    token = getpass.getpass("GitHub Personal Access Token: ")
    if not token.strip():
        console.print("[red]Token cannot be empty.[/red]")
        sys.exit(1)

    try:
        result = auth.authenticate_with_pat(token.strip())
    except AuthError as e:
        console.print(f"[red]Login failed:[/red] {e}")
        sys.exit(1)

    store.save(result.jwt, result.github_username)
    console.print(f"[green]Logged in as[/green] [bold]{result.github_username}[/bold]")


def _login_device_flow(auth: GitHubAuth, store: TokenStore) -> None:
    """Login with GitHub Device Flow."""
    try:
        device = auth.start_device_flow()
    except AuthError as e:
        console.print(f"[red]Failed to start device flow:[/red] {e}")
        sys.exit(1)

    console.print()
    console.print(f"Open [bold]{device.verification_uri}[/bold] in your browser")
    console.print(f"Enter code: [bold cyan]{device.user_code}[/bold cyan]")
    console.print()

    with console.status("Waiting for authorization..."):
        try:
            result = auth.poll_device_flow(
                device.device_code,
                device.interval,
                device.expires_in,
            )
        except AuthError as e:
            console.print(f"[red]Login failed:[/red] {e}")
            sys.exit(1)

    store.save(result.jwt, result.github_username)
    console.print(f"[green]Logged in as[/green] [bold]{result.github_username}[/bold]")


@main.command()
def whoami() -> None:
    """Show current authenticated identity."""
    cm = _get_config_manager()
    store = TokenStore(cm)

    if not store.is_logged_in:
        console.print("[yellow]Not logged in.[/yellow] Run [bold]toss login[/bold].")
        sys.exit(1)

    config = cm.load_config()
    auth = GitHubAuth(config.server.base_url, config.server.timeout)

    try:
        user_info = auth.get_user_info(store.jwt)  # type: ignore[arg-type]
    except AuthError as e:
        console.print(f"[red]Failed to fetch user info:[/red] {e}")
        console.print("Try [bold]toss login[/bold] again.")
        sys.exit(1)

    console.print(f"[bold]{user_info.get('github_username', 'unknown')}[/bold]")
    display = user_info.get("display_name")
    if display:
        console.print(f"  Name: {display}")
    console.print(f"  ID: {user_info.get('id', 'unknown')}")


@main.command()
def logout() -> None:
    """Remove stored credentials."""
    cm = _get_config_manager()
    store = TokenStore(cm)

    if not store.is_logged_in:
        console.print("[yellow]Not logged in.[/yellow]")
        return

    username = store.github_username
    store.clear()
    console.print(f"[green]Logged out[/green] ({username})")
