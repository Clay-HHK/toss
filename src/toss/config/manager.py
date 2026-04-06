"""Configuration file management for ~/.toss/ directory."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .models import TossConfig, ServerConfig, SyncConfig

logger = logging.getLogger(__name__)

DEFAULT_TOSS_DIR = "~/.toss"
CONFIG_FILENAME = "config.yaml"
CREDENTIALS_FILENAME = "credentials.yaml"


class ConfigManager:
    """Manages Toss configuration and credentials stored in ~/.toss/."""

    def __init__(self, base_dir: str | None = None) -> None:
        raw = base_dir or os.environ.get("TOSS_HOME", DEFAULT_TOSS_DIR)
        self.base_dir = Path(raw).expanduser()
        self._config_path = self.base_dir / CONFIG_FILENAME
        self._credentials_path = self.base_dir / CREDENTIALS_FILENAME

    @property
    def is_initialized(self) -> bool:
        return self._config_path.exists()

    def ensure_dirs(self) -> None:
        """Create the ~/.toss/ directory structure."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        spaces_dir = self.base_dir / "spaces"
        spaces_dir.mkdir(exist_ok=True)
        logger.info("Ensured directory: %s", self.base_dir)

    def load_config(self) -> TossConfig:
        """Load config from ~/.toss/config.yaml, return defaults if missing."""
        if not self._config_path.exists():
            return TossConfig()

        data = self._read_yaml(self._config_path)
        if not data:
            return TossConfig()

        server_data = data.get("server", {})
        sync_data = data.get("sync", {})

        server = ServerConfig(
            base_url=server_data.get("base_url", ServerConfig.base_url),
            timeout=server_data.get("timeout", ServerConfig.timeout),
        )

        ignore = sync_data.get("ignore_patterns")
        sync = SyncConfig(
            auto_sync=sync_data.get("auto_sync", SyncConfig.auto_sync),
            sync_interval_seconds=sync_data.get(
                "sync_interval_seconds", SyncConfig.sync_interval_seconds
            ),
            ignore_patterns=tuple(ignore) if ignore else SyncConfig.ignore_patterns,
        )

        return TossConfig(
            server=server,
            sync=sync,
            default_space=data.get("default_space"),
            spaces_dir=data.get("spaces_dir", TossConfig.spaces_dir),
        )

    def save_config(self, config: TossConfig) -> None:
        """Write config to ~/.toss/config.yaml."""
        data: dict[str, Any] = {
            "server": {
                "base_url": config.server.base_url,
                "timeout": config.server.timeout,
            },
            "sync": {
                "auto_sync": config.sync.auto_sync,
                "sync_interval_seconds": config.sync.sync_interval_seconds,
                "ignore_patterns": list(config.sync.ignore_patterns),
            },
            "spaces_dir": config.spaces_dir,
        }
        if config.default_space:
            data["default_space"] = config.default_space

        self._write_yaml(self._config_path, data)
        logger.info("Config saved to %s", self._config_path)

    def load_credentials(self) -> dict[str, str]:
        """Load credentials (JWT token, GitHub username)."""
        if not self._credentials_path.exists():
            return {}
        return self._read_yaml(self._credentials_path) or {}

    def save_credentials(self, credentials: dict[str, str]) -> None:
        """Write credentials with restricted file permissions (0600)."""
        self._write_yaml(self._credentials_path, credentials)
        self._credentials_path.chmod(0o600)
        logger.info("Credentials saved to %s", self._credentials_path)

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
