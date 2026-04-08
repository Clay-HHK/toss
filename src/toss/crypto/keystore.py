"""Private key persistence backends.

Phase A ships two concrete backends and an auto-detect factory:

- :class:`EnvKeyStore` — reads the seed from ``TOSS_PRIVATE_KEY``. Designed
  for MCP / CI / launchd where no interactive prompt is possible. Never
  writes anywhere.
- :class:`FileKeyStore` — reads / writes a 0600 file under
  ``~/.toss/keys/<profile>.seed``. The seed is stored base64url with no
  padding. This is the default for interactive CLI use in Phase A.

Future backends (deferred to later phases):

- ``KeychainKeyStore`` — macOS Keychain / Linux libsecret / Windows DPAPI
  via the ``keyring`` package
- ``PassphraseFileKeyStore`` — argon2id-derived wrap over a SecretBox

The abstract :class:`KeyStore` defines the tiny contract: load/save/exists.
Backends MUST raise :class:`KeyStoreError` for any unrecoverable problem so
callers can present a single error type to the user.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from .keypair import KeyPair, _b64u_decode, _b64u_encode

logger = logging.getLogger(__name__)

ENV_VAR_NAME = "TOSS_PRIVATE_KEY"
_DEFAULT_FILE_MODE = 0o600
_DEFAULT_DIR_MODE = 0o700


class KeyStoreError(Exception):
    """Raised for any unrecoverable keystore problem."""


class KeyStore(ABC):
    """Persistence contract for a single profile's keypair."""

    @abstractmethod
    def load(self) -> KeyPair | None:
        """Return the stored keypair, or ``None`` if absent."""

    @abstractmethod
    def save(self, keypair: KeyPair) -> None:
        """Persist `keypair`, overwriting any existing entry."""

    @abstractmethod
    def exists(self) -> bool:
        """Whether a keypair is currently stored."""

    @abstractmethod
    def delete(self) -> None:
        """Remove any stored keypair. No-op if absent."""


class EnvKeyStore(KeyStore):
    """Read-only backend that sources the seed from an environment variable.

    Never writes. ``save()`` is a no-op with a warning — if the process is
    running under MCP/CI and tries to persist a new key, that's a
    configuration bug the caller should handle.
    """

    def __init__(self, env_var: str = ENV_VAR_NAME):
        self._env_var = env_var

    def load(self) -> KeyPair | None:
        raw = os.environ.get(self._env_var)
        if not raw:
            return None
        try:
            return KeyPair.from_seed_b64(raw.strip())
        except Exception as e:
            raise KeyStoreError(f"{self._env_var} is set but not a valid seed: {e}") from e

    def save(self, keypair: KeyPair) -> None:  # noqa: ARG002 — intentional no-op
        logger.warning(
            "EnvKeyStore.save() is a no-op; set %s in your environment to persist",
            self._env_var,
        )

    def exists(self) -> bool:
        return bool(os.environ.get(self._env_var))

    def delete(self) -> None:
        logger.warning("EnvKeyStore.delete() is a no-op; unset %s externally", self._env_var)


class FileKeyStore(KeyStore):
    """Plain on-disk backend.

    The seed is stored base64url-encoded (no padding) in a single file. The
    file is created with 0600 perms and the parent directory with 0700. The
    contents are NOT encrypted at rest — on Phase A this is an acceptable
    tradeoff for ease of use. Migrate to ``KeychainKeyStore`` for higher
    assurance.
    """

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> KeyPair | None:
        if not self._path.exists():
            return None
        try:
            raw = self._path.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise KeyStoreError(f"cannot read {self._path}: {e}") from e
        if not raw:
            return None
        try:
            return KeyPair.from_seed(_b64u_decode(raw))
        except Exception as e:
            raise KeyStoreError(f"seed file {self._path} is malformed: {e}") from e

    def save(self, keypair: KeyPair) -> None:
        parent = self._path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(parent, _DEFAULT_DIR_MODE)
            except OSError:
                pass
            self._path.write_text(_b64u_encode(keypair.seed), encoding="utf-8")
            try:
                os.chmod(self._path, _DEFAULT_FILE_MODE)
            except OSError:
                pass
        except OSError as e:
            raise KeyStoreError(f"cannot write {self._path}: {e}") from e

    def exists(self) -> bool:
        return self._path.exists() and self._path.stat().st_size > 0

    def delete(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError as e:
            raise KeyStoreError(f"cannot delete {self._path}: {e}") from e


def auto_detect_keystore(
    config_dir: Path,
    profile: str = "default",
    *,
    prefer_env: bool = True,
) -> KeyStore:
    """Pick the best available backend for the current environment.

    Order (when ``prefer_env=True``, the default):

    1. :class:`EnvKeyStore` if ``TOSS_PRIVATE_KEY`` is set (MCP / CI path)
    2. :class:`FileKeyStore` at ``<config_dir>/keys/<profile>.seed``

    This is intentionally simple. ``KeychainKeyStore`` is a future extension
    point that slots in ahead of :class:`FileKeyStore` when available.
    """
    if prefer_env and os.environ.get(ENV_VAR_NAME):
        return EnvKeyStore()
    return FileKeyStore(config_dir / "keys" / f"{profile}.seed")
