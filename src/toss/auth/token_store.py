"""Local JWT token storage."""

from __future__ import annotations

import logging

from toss.config.manager import ConfigManager

logger = logging.getLogger(__name__)


class TokenStore:
    """Read/write JWT and identity from ~/.toss/credentials.yaml."""

    def __init__(self, config_manager: ConfigManager) -> None:
        self._cm = config_manager

    @property
    def jwt(self) -> str | None:
        creds = self._cm.load_credentials()
        return creds.get("jwt")

    @property
    def github_username(self) -> str | None:
        creds = self._cm.load_credentials()
        return creds.get("github_username")

    @property
    def is_logged_in(self) -> bool:
        return self.jwt is not None

    def save(self, jwt: str, github_username: str) -> None:
        """Store JWT and GitHub identity."""
        self._cm.save_credentials({
            "jwt": jwt,
            "github_username": github_username,
        })
        logger.info("Credentials stored for %s", github_username)

    def clear(self) -> None:
        """Remove stored credentials."""
        self._cm.save_credentials({})
        logger.info("Credentials cleared")
