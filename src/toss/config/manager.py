"""Configuration file management for ~/.toss/ directory."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .models import ServerConfig, SyncConfig, TossConfig

logger = logging.getLogger(__name__)

DEFAULT_TOSS_DIR = "~/.toss"
CONFIG_FILENAME = "config.yaml"
CREDENTIALS_FILENAME = "credentials.yaml"
DEFAULT_PROFILE = "default"


class ConfigManager:
    """Manages Toss configuration and credentials stored in ~/.toss/.

    Config format (multi-profile):

        current_profile: work
        profiles:
          work:
            server:
              base_url: https://work.workers.dev
              timeout: 30
          lab:
            server:
              base_url: https://lab.workers.dev
        sync:
          auto_sync: false
        spaces_dir: ~/.toss/spaces

    Old single-server configs are migrated to a ``default`` profile on first read.
    """

    def __init__(self, base_dir: str | None = None) -> None:
        raw = base_dir or os.environ.get("TOSS_HOME", DEFAULT_TOSS_DIR)
        self.base_dir = Path(raw).expanduser()
        self._config_path = self.base_dir / CONFIG_FILENAME
        self._credentials_path = self.base_dir / CREDENTIALS_FILENAME

    # ------------------------------------------------------------------
    # Basic properties
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._config_path.exists()

    def ensure_dirs(self) -> None:
        """Create the ~/.toss/ directory structure."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "spaces").mkdir(exist_ok=True)
        logger.info("Ensured directory: %s", self.base_dir)

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    @property
    def current_profile_name(self) -> str:
        """Return the name of the currently active profile."""
        if not self._config_path.exists():
            return DEFAULT_PROFILE
        data = self._read_yaml(self._config_path)
        return data.get("current_profile", DEFAULT_PROFILE)

    def list_profiles(self) -> list[str]:
        """Return all profile names in config order."""
        if not self._config_path.exists():
            return []
        data = self._migrate_config_if_needed(self._read_yaml(self._config_path))
        return list(data.get("profiles", {}).keys())

    def switch_profile(self, name: str) -> None:
        """Set ``name`` as the active profile.

        Raises:
            KeyError: If the profile does not exist.
        """
        data = self._migrate_config_if_needed(self._read_yaml(self._config_path))
        if name not in data.get("profiles", {}):
            raise KeyError(f"Profile '{name}' not found")
        data["current_profile"] = name
        self._write_yaml(self._config_path, data)
        logger.info("Switched to profile: %s", name)

    def add_profile(self, name: str, base_url: str, timeout: int = 30) -> None:
        """Add (or overwrite) a profile with the given server URL.

        If this is the first profile, it is set as current.

        Raises:
            ValueError: If ``name`` contains illegal characters.
        """
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Profile name '{name}' must be alphanumeric (hyphens/underscores ok)")
        raw = self._read_yaml(self._config_path) if self._config_path.exists() else {}
        data = self._migrate_config_if_needed(raw)
        profiles = data.setdefault("profiles", {})
        profiles[name] = {"server": {"base_url": base_url, "timeout": timeout}}
        if "current_profile" not in data:
            data["current_profile"] = name
        self._write_yaml(self._config_path, data)
        logger.info("Added profile '%s' -> %s", name, base_url)

    def remove_profile(self, name: str) -> None:
        """Remove a profile and its stored credentials.

        Raises:
            KeyError: If the profile does not exist.
            ValueError: If trying to remove the currently active profile.
        """
        data = self._migrate_config_if_needed(self._read_yaml(self._config_path))
        profiles = data.get("profiles", {})
        if name not in profiles:
            raise KeyError(f"Profile '{name}' not found")
        if data.get("current_profile") == name:
            raise ValueError(f"Cannot remove active profile '{name}'. Switch to another first.")
        del profiles[name]
        self._write_yaml(self._config_path, data)

        # Remove credentials for this profile
        if self._credentials_path.exists():
            creds = self._read_yaml(self._credentials_path)
            creds.pop(name, None)
            self._write_yaml(self._credentials_path, creds)
            self._credentials_path.chmod(0o600)

        logger.info("Removed profile: %s", name)

    # ------------------------------------------------------------------
    # Config read/write (profile-aware)
    # ------------------------------------------------------------------

    def load_config(self) -> TossConfig:
        """Load config for the current profile, return defaults if missing."""
        if not self._config_path.exists():
            return TossConfig()

        raw = self._read_yaml(self._config_path)
        if not raw:
            return TossConfig()

        data = self._migrate_config_if_needed(raw)
        current = data.get("current_profile", DEFAULT_PROFILE)
        server_data = data.get("profiles", {}).get(current, {}).get("server", {})
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
        """Write TossConfig for the current profile back to disk."""
        data = self._migrate_config_if_needed(
            self._read_yaml(self._config_path) if self._config_path.exists() else {}
        )
        current = data.get("current_profile", DEFAULT_PROFILE)
        data.setdefault("profiles", {}).setdefault(current, {})["server"] = {
            "base_url": config.server.base_url,
            "timeout": config.server.timeout,
        }
        data["sync"] = {
            "auto_sync": config.sync.auto_sync,
            "sync_interval_seconds": config.sync.sync_interval_seconds,
            "ignore_patterns": list(config.sync.ignore_patterns),
        }
        data["spaces_dir"] = config.spaces_dir
        if config.default_space:
            data["default_space"] = config.default_space
        self._write_yaml(self._config_path, data)
        logger.info("Config saved (profile=%s)", current)

    def get_default_space(self) -> str | None:
        return self.load_config().default_space

    def set_default_space(self, slug: str) -> None:
        config = self.load_config()
        updated = TossConfig(
            server=config.server,
            sync=config.sync,
            default_space=slug,
            spaces_dir=config.spaces_dir,
        )
        self.save_config(updated)
        logger.info("Default space set to %s", slug)

    # ------------------------------------------------------------------
    # Credentials (profile-aware)
    # ------------------------------------------------------------------

    def load_credentials(self) -> dict[str, str]:
        """Load JWT and GitHub username for the current profile."""
        if not self._credentials_path.exists():
            return {}
        raw = self._read_yaml(self._credentials_path) or {}
        current = self.current_profile_name
        raw = self._migrate_credentials_if_needed(raw, current)
        return raw.get(current, {})

    def save_credentials(self, credentials: dict[str, str]) -> None:
        """Write credentials for the current profile (0600 permissions)."""
        current = self.current_profile_name
        if self._credentials_path.exists():
            data = self._read_yaml(self._credentials_path) or {}
            data = self._migrate_credentials_if_needed(data, current)
        else:
            data = {}
        data[current] = credentials
        self._write_yaml(self._credentials_path, data)
        self._credentials_path.chmod(0o600)
        logger.info("Credentials saved (profile=%s)", current)

    # ------------------------------------------------------------------
    # Migration helpers
    # ------------------------------------------------------------------

    def _migrate_config_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert old flat config (server.base_url at top level) to profiles format."""
        if "profiles" in data or not data:
            return data
        # Old format detected: lift server into default profile
        old_server = data.pop("server", {})
        data["profiles"] = {DEFAULT_PROFILE: {"server": old_server}}
        data["current_profile"] = DEFAULT_PROFILE
        if self._config_path.exists():
            self._write_yaml(self._config_path, data)
            logger.info("Migrated config to profiles format (profile=%s)", DEFAULT_PROFILE)
        return data

    def _migrate_credentials_if_needed(
        self, data: dict[str, Any], current: str
    ) -> dict[str, Any]:
        """Convert old flat credentials (jwt at top level) to per-profile format."""
        if "jwt" not in data:
            return data
        migrated = {current: {"jwt": data["jwt"], "github_username": data.get("github_username", "")}}
        self._write_yaml(self._credentials_path, migrated)
        self._credentials_path.chmod(0o600)
        logger.info("Migrated credentials to per-profile format (profile=%s)", current)
        return migrated

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
