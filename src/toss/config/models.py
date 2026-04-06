"""Configuration dataclasses for Toss."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServerConfig:
    """Remote Toss Worker API configuration."""

    base_url: str = "https://toss-api.workers.dev"
    timeout: int = 30


@dataclass(frozen=True)
class SyncConfig:
    """Shared space sync settings."""

    auto_sync: bool = False
    sync_interval_seconds: int = 300
    ignore_patterns: tuple[str, ...] = (
        ".DS_Store",
        "__pycache__",
        "*.pyc",
        ".git",
        ".toss-sync.yaml",
    )


@dataclass(frozen=True)
class TossConfig:
    """Top-level Toss configuration."""

    server: ServerConfig = field(default_factory=ServerConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    default_space: str | None = None
    spaces_dir: str = "~/.toss/spaces"
