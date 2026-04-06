"""Interactive inbox browser with vim-like keybindings."""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from toss.client.base import TossAPIError
from toss.client.documents import DocumentClient

console = Console()


def _read_key() -> str:
    """Read a single keypress without waiting for Enter."""
    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        return "q"

    import termios
    import tty

    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrow keys)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "esc"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"


def _render_list(items: list[dict[str, Any]], cursor: int) -> None:
    """Render the inbox list with the current cursor position."""
    console.clear()
    console.print(f"[bold] Inbox ({len(items)} pending)[/bold]\n")

    for i, item in enumerate(items):
        filename = item.get("filename", "?")
        sender = f"@{item.get('sender_username', '?')}"
        size = _human_size(item.get("size_bytes", 0))
        msg = item.get("message") or ""
        time = item.get("created_at", "")[:16]

        if len(filename) > 28:
            filename = filename[:25] + "..."
        if len(msg) > 20:
            msg = msg[:17] + "..."

        line = f"  {filename:<28} {sender:<14} {size:<8} {msg:<20} {time}"

        if i == cursor:
            console.print(f"[black on white]{line}[/black on white]")
        else:
            console.print(line)

    console.print()
    console.print(
        "[dim]  j/↓ down  k/↑ up  Enter preview"
        "  p pull  d delete  a pull all  q quit[/dim]"
    )


def _render_preview(item: dict[str, Any], preview_data: dict[str, Any]) -> None:
    """Render the preview screen."""
    console.clear()

    filename = preview_data.get("filename", item.get("filename", "?"))
    sender = f"@{item.get('sender_username', '?')}"
    size = _human_size(preview_data.get("size_bytes", item.get("size_bytes", 0)))
    ctype = preview_data.get("content_type", "")

    header = f"{filename}  from {sender}  {size}  [{ctype}]"
    console.print(f"[bold]{header}[/bold]\n")

    if preview_data.get("preview_type") == "text":
        content = preview_data.get("content", "")
        # Wrap long lines for readability
        width = min(console.width - 4, 120)
        lines = content.splitlines()
        display_lines: list[str] = []
        max_lines = console.height - 8
        for line in lines:
            wrapped = textwrap.wrap(line, width=width) or [""]
            display_lines.extend(wrapped)
            if len(display_lines) >= max_lines:
                break

        text = "\n".join(display_lines[:max_lines])
        if preview_data.get("truncated") or len(display_lines) > max_lines:
            text += "\n[dim]... (truncated)[/dim]"

        console.print(Panel(text, border_style="blue", expand=False))
    else:
        console.print(
            Panel(
                f"[yellow]Binary file ({ctype}). Pull to view locally.[/yellow]",
                border_style="yellow",
                expand=False,
            )
        )

    console.print()
    console.print("[dim]  q/Esc back  p pull this file  d delete[/dim]")


def run_inbox_browser(dc: DocumentClient, items: list[dict[str, Any]]) -> None:
    """Run the interactive inbox browser."""
    cursor = 0
    mode = "list"  # "list" or "preview"
    current_preview: dict[str, Any] = {}

    _render_list(items, cursor)

    while True:
        key = _read_key()

        if mode == "list":
            if key in ("q", "\x03"):  # q or Ctrl-C
                console.clear()
                break
            elif key in ("j", "down"):
                cursor = min(cursor + 1, len(items) - 1)
                _render_list(items, cursor)
            elif key in ("k", "up"):
                cursor = max(cursor - 1, 0)
                _render_list(items, cursor)
            elif key in ("\r", "\n"):  # Enter - preview
                item = items[cursor]
                console.clear()
                console.print("[dim]Loading preview...[/dim]")
                try:
                    current_preview = dc.preview(item["id"])
                    mode = "preview"
                    _render_preview(item, current_preview)
                except TossAPIError as e:
                    _render_list(items, cursor)
                    console.print(f"\n[red]Preview failed: {e.detail}[/red]")
            elif key == "p":  # Pull selected
                item = items[cursor]
                dest_dir = Path.cwd()
                console.clear()
                console.print(f"[dim]Pulling {item.get('filename', '?')}...[/dim]")
                try:
                    path = dc.pull(item["id"], dest_dir)
                    items.pop(cursor)
                    if cursor >= len(items) and cursor > 0:
                        cursor -= 1
                    if not items:
                        console.clear()
                        console.print("[green]All files pulled. Inbox empty.[/green]")
                        break
                    _render_list(items, cursor)
                    console.print(f"\n[green]Pulled[/green] {path.name} -> {dest_dir}")
                except TossAPIError as e:
                    _render_list(items, cursor)
                    console.print(f"\n[red]Pull failed: {e.detail}[/red]")
            elif key == "d":  # Delete selected
                item = items[cursor]
                _render_list(items, cursor)
                console.print(
                    f"\n[yellow]Delete {item.get('filename', '?')}?"
                    " (y to confirm)[/yellow]"
                )
                confirm = _read_key()
                if confirm == "y":
                    try:
                        dc.delete(item["id"])
                        items.pop(cursor)
                        if cursor >= len(items) and cursor > 0:
                            cursor -= 1
                        if not items:
                            console.clear()
                            console.print("[green]Inbox empty.[/green]")
                            break
                        _render_list(items, cursor)
                        console.print(
                            f"\n[yellow]Deleted[/yellow]"
                            f" {item.get('filename', '?')}"
                        )
                    except TossAPIError as e:
                        _render_list(items, cursor)
                        console.print(f"\n[red]Delete failed: {e.detail}[/red]")
                else:
                    _render_list(items, cursor)
            elif key == "a":  # Pull all
                console.clear()
                dest_dir = Path.cwd()
                console.print(f"Pulling {len(items)} file(s)...\n")
                for item in items:
                    try:
                        path = dc.pull(item["id"], dest_dir)
                        console.print(
                            f"  [green]Pulled[/green] {path.name}"
                            f" (from @{item.get('sender_username', '?')})"
                        )
                    except TossAPIError as e:
                        console.print(
                            f"  [red]Failed[/red]"
                            f" {item.get('filename', '?')}: {e.detail}"
                        )
                console.print(f"\n[green]Done.[/green] Files saved to {dest_dir}")
                break

        elif mode == "preview":
            if key in ("q", "esc", "\x1b", "\x03"):  # Back to list
                mode = "list"
                _render_list(items, cursor)
            elif key == "p":  # Pull from preview
                item = items[cursor]
                dest_dir = Path.cwd()
                console.clear()
                console.print(f"[dim]Pulling {item.get('filename', '?')}...[/dim]")
                try:
                    path = dc.pull(item["id"], dest_dir)
                    items.pop(cursor)
                    if cursor >= len(items) and cursor > 0:
                        cursor -= 1
                    if not items:
                        console.clear()
                        console.print("[green]All files pulled. Inbox empty.[/green]")
                        break
                    mode = "list"
                    _render_list(items, cursor)
                    console.print(f"\n[green]Pulled[/green] {path.name} -> {dest_dir}")
                except TossAPIError as e:
                    mode = "list"
                    _render_list(items, cursor)
                    console.print(f"\n[red]Pull failed: {e.detail}[/red]")
            elif key == "d":  # Delete from preview
                item = items[cursor]
                console.print(
                    f"\n[yellow]Delete {item.get('filename', '?')}?"
                    " (y to confirm)[/yellow]"
                )
                confirm = _read_key()
                if confirm == "y":
                    try:
                        dc.delete(item["id"])
                        items.pop(cursor)
                        if cursor >= len(items) and cursor > 0:
                            cursor -= 1
                        if not items:
                            console.clear()
                            console.print("[green]Inbox empty.[/green]")
                            break
                        mode = "list"
                        _render_list(items, cursor)
                        console.print(
                            f"\n[yellow]Deleted[/yellow]"
                            f" {item.get('filename', '?')}"
                        )
                    except TossAPIError as e:
                        mode = "list"
                        _render_list(items, cursor)
                        console.print(f"\n[red]Delete failed: {e.detail}[/red]")
                else:
                    _render_preview(item, current_preview)
