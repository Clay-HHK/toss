"""Toss CLI entry point: init, login, whoami, switch commands."""

from __future__ import annotations

import getpass
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

import click
from rich.console import Console

from toss.auth.github import AuthError, GitHubAuth
from toss.auth.token_store import TokenStore
from toss.cli.contacts import contacts
from toss.cli.groups import group
from toss.cli.profiles import profile
from toss.cli.push_pull import inbox, pull, push
from toss.cli.spaces import space
from toss.client.base import TossAPIError, TossClient
from toss.client.groups import GroupClient
from toss.config.manager import ConfigManager
from toss.config.models import ServerConfig, TossConfig
from toss.crypto.enroll import EnrollError, ensure_enrolled
from toss.crypto.keystore import auto_detect_keystore

console = Console()


def _get_config_manager() -> ConfigManager:
    return ConfigManager()


def _install_claude_hooks() -> None:
    """Write Toss hooks into ~/.claude/settings.json (merge, don't overwrite)."""
    hooks_dir = Path(__file__).resolve().parents[3] / "hooks"
    inbox_hook = str(hooks_dir / "toss-inbox-check.sh")
    sync_hook = str(hooks_dir / "toss-sync.sh")

    settings_path = Path.home() / ".claude" / "settings.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    hooks = settings.setdefault("hooks", {})

    session_start: list[dict[str, Any]] = hooks.setdefault("SessionStart", [])
    inbox_entry = {"type": "command", "command": inbox_hook}
    if not _hook_exists(session_start, inbox_hook):
        session_start.append(inbox_entry)

    post_tool: list[dict[str, Any]] = hooks.setdefault("PostToolUse", [])
    sync_entry = {"type": "command", "command": sync_hook, "matcher": "Write|Edit"}
    if not _hook_exists(post_tool, sync_hook):
        post_tool.append(sync_entry)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    console.print(f"[green]Hooks installed[/green] in {settings_path}")


def _hook_exists(hook_list: list[dict[str, Any]], command: str) -> bool:
    return any(h.get("command") == command for h in hook_list)


@click.group(invoke_without_command=True)
@click.version_option(package_name="toss")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Toss: Agent-to-Agent document sharing tool."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Register subcommands
main.add_command(contacts)
main.add_command(group)
main.add_command(profile)
main.add_command(push)
main.add_command(pull)
main.add_command(inbox)
main.add_command(space)


@main.command()
@click.option(
    "--install-hooks",
    is_flag=True,
    default=False,
    help="Install Claude Code hooks for inbox check and auto-sync.",
)
def init(install_hooks: bool) -> None:
    """Initialize Toss configuration directory (~/.toss/)."""
    cm = _get_config_manager()

    if cm.is_initialized:
        console.print("[yellow]Already initialized.[/yellow]", f"Config dir: {cm.base_dir}")
    else:
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

    if install_hooks:
        _install_claude_hooks()


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
    token = getpass.getpass("GitHub Personal Access Token: ")
    if not token.strip():
        console.print("[red]Token cannot be empty.[/red]")
        sys.exit(1)

    try:
        # T1-4: bind the issued JWT to this device id so we can revoke it
        # individually later via `toss logout`.
        device_id = store._cm.load_or_create_device_id()
        result = auth.authenticate_with_pat(token.strip(), device_id=device_id)
    except AuthError as e:
        console.print(f"[red]Login failed:[/red] {e}")
        sys.exit(1)

    store.save(result.jwt, result.github_username)
    console.print(f"[green]Logged in as[/green] [bold]{result.github_username}[/bold]")
    _enroll_keypair_after_login(store, result.jwt, result.github_username)


def _login_device_flow(auth: GitHubAuth, store: TokenStore) -> None:
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
            device_id = store._cm.load_or_create_device_id()
            result = auth.poll_device_flow(
                device.device_code,
                device.interval,
                device.expires_in,
                device_id=device_id,
            )
        except AuthError as e:
            console.print(f"[red]Login failed:[/red] {e}")
            sys.exit(1)

    store.save(result.jwt, result.github_username)
    console.print(f"[green]Logged in as[/green] [bold]{result.github_username}[/bold]")
    _enroll_keypair_after_login(store, result.jwt, result.github_username)


def _enroll_keypair_after_login(
    store: TokenStore, jwt: str, github_username: str,
) -> None:
    """T2-4 Phase A: opportunistically publish the local keypair.

    Enrollment is best-effort:

    - Server that does not advertise ``pubkey-directory`` -> silent skip
    - Server unreachable, proof rejected, keystore write failure -> warn
      the user but **do not** abort login. Phase A still works without a
      published key (plaintext path).
    """
    cm = store._cm
    client = TossClient.from_config(cm)
    try:
        features = client.fetch_features() or None
    except Exception as e:
        logger.debug("Feature probe failed during enrollment: %s", e)
        features = None

    keystore = auto_detect_keystore(cm.base_dir, profile=cm.current_profile_name)

    try:
        result = ensure_enrolled(
            api_base_url=cm.load_config().server.base_url,
            jwt=jwt,
            github_username=github_username,
            keystore=keystore,
            server_features=features,
        )
    except EnrollError as e:
        console.print(f"[yellow]Key enrollment skipped:[/yellow] {e}")
        return
    except Exception as e:  # keystore / network surprises
        logger.warning("Enrollment failed unexpectedly: %s", e)
        console.print(f"[yellow]Key enrollment skipped:[/yellow] {e}")
        return

    if result.skipped_reason:
        logger.info("Enrollment skipped: %s", result.skipped_reason)
        return
    if result.new_enrollment:
        console.print(
            "[green]Published new encryption key[/green] "
            f"(fingerprint [bold]{result.keypair.fingerprint()}[/bold]). "
            "Back it up with [bold]toss keys export[/bold].",
        )
    else:
        logger.info(
            "Key already enrolled (fingerprint=%s)",
            result.keypair.fingerprint(),
        )


@main.command()
def whoami() -> None:
    """Show current identity and active profile."""
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
        console.print(f"  Name:    {display}")
    console.print(f"  ID:      {user_info.get('id', 'unknown')}")
    console.print(f"  Profile: [cyan]{cm.current_profile_name}[/cyan]")
    console.print(f"  Server:  {config.server.base_url}")


@main.command()
def logout() -> None:
    """Revoke the current token on the server, then clear local credentials."""
    cm = _get_config_manager()
    store = TokenStore(cm)

    if not store.is_logged_in:
        console.print("[yellow]Not logged in.[/yellow]")
        return

    username = store.github_username

    # T1-4: best-effort server-side revoke before wiping local creds. If the
    # server is unreachable, the blacklist entry will be missing but the
    # token is already useless because we're deleting it from the client.
    try:
        client = TossClient.from_config(cm)
        client.revoke_current_token()
    except TossAPIError as e:
        console.print(f"[yellow]Could not revoke token on server:[/yellow] {e}")
        console.print("Continuing with local logout.")
    except Exception as e:  # pragma: no cover — network / env noise
        logger.debug("Revoke failed during logout: %s", e)

    store.clear()
    console.print(f"[green]Logged out[/green] ({username})")


@main.command()
@click.argument("name")
def switch(name: str) -> None:
    """Switch the active profile (work team).

    \b
    Example:
        toss switch work
        toss switch lab
    """
    cm = _get_config_manager()
    try:
        cm.switch_profile(name)
    except KeyError:
        profiles = cm.list_profiles()
        console.print(f"[red]Profile '{name}' not found.[/red]")
        if profiles:
            console.print(f"Available: {', '.join(profiles)}")
        else:
            console.print("No profiles configured. Use [bold]toss join[/bold] to add one.")
        sys.exit(1)

    config = cm.load_config()
    store = TokenStore(cm)
    logged_in = store.is_logged_in
    status = f"[green]logged in as {store.github_username}[/green]" if logged_in else "[yellow]not logged in[/yellow]"

    console.print(f"[green]Switched[/green] to profile [bold cyan]{name}[/bold cyan]")
    console.print(f"  Server: {config.server.base_url}")
    console.print(f"  Auth:   {status}")

    if not logged_in:
        console.print("\nRun [bold]toss login --pat[/bold] to authenticate for this profile.")


@main.command()
@click.argument("invite_code")
@click.option("--profile-name", "-p", default=None, help="Name for this team profile (default: auto-derived from server host)")
def join(invite_code: str, profile_name: str | None) -> None:
    """Join a group with one command (auto-configures everything).

    The invite code contains the server address.

    \b
    Example:
        toss join toss-api.example.workers.dev/ABCD-1234
        toss join toss-api.example.workers.dev/ABCD-1234 --profile-name work
    """
    if "/" not in invite_code:
        console.print(
            "[red]Error:[/red] Invite code must include server address.\n"
            "  Format: server.example.com/ABCD-1234"
        )
        sys.exit(1)

    parts = invite_code.rsplit("/", 1)
    server_host = parts[0]
    code = parts[1]
    base_url = f"https://{server_host}"

    # Derive a profile name from the server hostname if not given
    if not profile_name:
        profile_name = server_host.split(".")[0].replace("-", "_")

    cm = _get_config_manager()
    if not cm.is_initialized:
        cm.ensure_dirs()
        console.print("[green]Initialized[/green] ~/.toss/")

    # Register this server as a named profile and switch to it
    cm.add_profile(profile_name, base_url)
    cm.switch_profile(profile_name)
    console.print(f"[green]Configured[/green] profile [bold]{profile_name}[/bold] -> {base_url}")

    # Login if not already authenticated for this profile
    store = TokenStore(cm)
    if not store.is_logged_in:
        console.print("\n[bold]Login required.[/bold] Authenticate with GitHub:")
        token = getpass.getpass("  GitHub Personal Access Token: ")
        if not token.strip():
            console.print("[red]Token cannot be empty.[/red]")
            sys.exit(1)

        auth = GitHubAuth(base_url, 30)
        try:
            result = auth.authenticate_with_pat(token.strip())
        except AuthError as e:
            console.print(f"[red]Login failed:[/red] {e}")
            sys.exit(1)

        store.save(result.jwt, result.github_username)
        console.print(f"[green]Logged in as[/green] [bold]{result.github_username}[/bold]")

    # Join the group
    try:
        client = TossClient.from_config(cm)
        gc = GroupClient(client)
        result = gc.join(code)
        console.print(
            f"\n[green]{result.get('message', 'Joined')}[/green]"
            f" group [bold]{result.get('group_name', '?')}[/bold]"
        )
        console.print("\nYou're all set! Try:")
        console.print("  [bold]toss inbox[/bold]            - check for files")
        console.print("  [bold]toss group list[/bold]       - see your groups")
        console.print("  [bold]toss profile list[/bold]     - see all your teams")
        console.print(f"  [bold]toss switch <name>[/bold]   - switch between teams")
    except TossAPIError as e:
        console.print(f"[red]Failed to join:[/red] {e.detail}")
        sys.exit(1)
