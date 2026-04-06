"""Push, pull, and inbox CLI commands with interactive modes."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary
from rich.console import Console
from rich.table import Table

from toss.client.base import TossAPIError, TossClient
from toss.client.documents import DocumentClient
from toss.config.manager import ConfigManager

console = Console()

# File extensions worth showing in the picker
_USEFUL_EXTENSIONS = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml",
    ".py", ".ts", ".js", ".html", ".css", ".tex", ".bib",
    ".pdf", ".png", ".jpg", ".jpeg", ".zip", ".tar", ".gz",
    ".toml", ".cfg", ".ini", ".xml", ".sql", ".sh",
    ".ipynb", ".r", ".R", ".jl", ".m",
}


def _get_doc_client() -> DocumentClient:
    client = TossClient.from_config(ConfigManager())
    return DocumentClient(client)


def _list_files_for_picker(directory: Path) -> list[Path]:
    """List files in directory suitable for pushing, sorted by modified time."""
    files: list[Path] = []
    for p in directory.iterdir():
        if p.name.startswith("."):
            continue
        if p.is_file() and (p.suffix.lower() in _USEFUL_EXTENSIONS or p.suffix == ""):
            files.append(p)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def _interactive_push() -> None:
    """Interactive mode: select files and recipient."""
    cwd = Path.cwd()

    # 1. Pick files
    files = _list_files_for_picker(cwd)
    if not files:
        console.print(f"[yellow]No files found in {cwd}[/yellow]")
        console.print("Try running from a directory with files, or specify paths directly:")
        console.print("  toss push /path/to/file.md recipient")
        return

    choices = [
        questionary.Choice(
            title=f"{f.name}  ({_human_size(f.stat().st_size)})",
            value=str(f),
        )
        for f in files[:20]  # Show at most 20 recent files
    ]

    selected = questionary.checkbox(
        "Select files to push (Space to select, Enter to confirm):",
        choices=choices,
    ).ask()

    if not selected:
        console.print("[yellow]No files selected.[/yellow]")
        return

    # 2. Pick recipient
    try:
        client = TossClient.from_config(ConfigManager())
        from toss.client.contacts import ContactClient
        cc = ContactClient(client)
        contacts = cc.list()
    except TossAPIError:
        contacts = []

    if contacts:
        contact_choices = [
            questionary.Choice(
                title=f"{c.get('alias', '')}  (@{c.get('github_username', '')})",
                value=c.get("alias", c.get("github_username", "")),
            )
            for c in contacts
        ]
        contact_choices.append(questionary.Choice(title="Enter manually...", value="__manual__"))

        recipient = questionary.select(
            "Send to:",
            choices=contact_choices,
        ).ask()

        if recipient == "__manual__":
            recipient = questionary.text("Recipient (alias or @github username):").ask()
    else:
        recipient = questionary.text("Recipient (alias or @github username):").ask()

    if not recipient:
        console.print("[yellow]No recipient specified.[/yellow]")
        return

    # 3. Optional message
    message = questionary.text("Message (optional, Enter to skip):").ask()
    if not message:
        message = None

    # 4. Push
    dc = DocumentClient(client)
    for file_str in selected:
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
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.argument("recipient", required=False, default=None)
@click.option("--message", "-m", default=None, help="Attach a message")
def push(files: tuple[str, ...], recipient: str | None, message: str | None) -> None:
    """Push files to a recipient.

    Interactive mode (no arguments): browse and select files, then pick recipient.
    Direct mode: toss push file1.md file2.md recipient [-m message]
    """
    # Interactive mode: no args
    if not files and not recipient:
        try:
            _interactive_push()
        except TossAPIError as e:
            console.print(f"[red]Error:[/red] {e.detail}")
            sys.exit(1)
        return

    # Direct mode: need recipient
    if not recipient:
        console.print("[red]Error:[/red] Specify a recipient as the last argument.")
        console.print("  toss push file.md recipient")
        console.print("  toss push  (interactive mode)")
        sys.exit(1)

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
@click.option("--pick", is_flag=True, help="Interactively select which files to pull")
def pull(dest: str, pick: bool) -> None:
    """Pull documents from inbox.

    By default pulls everything. Use --pick to select which files to download.
    """
    try:
        dc = _get_doc_client()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    try:
        items = dc.list_inbox()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print("[yellow]Inbox empty.[/yellow]")
        return

    # Interactive pick mode
    if pick:
        choices = [
            questionary.Choice(
                title=(
                    f"{it.get('filename', '?')}  "
                    f"({_human_size(it.get('size_bytes', 0))}, "
                    f"from @{it.get('sender_username', '?')})"
                ),
                value=it,
            )
            for it in items
        ]

        selected = questionary.checkbox(
            "Select files to pull (Space to select, Enter to confirm):",
            choices=choices,
        ).ask()

        if not selected:
            console.print("[yellow]No files selected.[/yellow]")
            return

        items = selected

    # Ask destination if in pick mode and dest is default
    if pick and dest == ".":
        custom_dest = questionary.text(
            "Save to (Enter for current directory):",
            default=".",
        ).ask()
        if custom_dest:
            dest = custom_dest

    dest_dir = Path(dest).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

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
@click.option("--plain", is_flag=True, help="Non-interactive table output")
def inbox(plain: bool) -> None:
    """Browse your inbox. Navigate with j/k, Enter to preview, p to pull."""
    try:
        dc = _get_doc_client()
        items = dc.list_inbox()
    except TossAPIError as e:
        console.print(f"[red]Error:[/red] {e.detail}")
        sys.exit(1)

    if not items:
        console.print("[yellow]Inbox empty.[/yellow]")
        return

    # Non-interactive mode (piped output, --plain flag, or non-TTY)
    if plain or not sys.stdout.isatty():
        _print_inbox_table(items)
        return

    from toss.cli.inbox_tui import run_inbox_browser

    run_inbox_browser(dc, items)


def _print_inbox_table(items: list[dict]) -> None:
    """Static table output for non-interactive use."""
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
