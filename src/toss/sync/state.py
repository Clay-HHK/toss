"""Sync state: manifest computation and .toss-sync.yaml persistence."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SYNC_STATE_FILENAME = ".toss-sync.yaml"


def compute_manifest(
    directory: Path,
    ignore_patterns: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Walk directory and compute SHA-256 manifest for all non-ignored files.

    Args:
        directory: Root directory to scan.
        ignore_patterns: Glob patterns to skip (matched against relative path parts).

    Returns:
        List of dicts with keys: path (POSIX relative), content_hash (hex), size_bytes.
    """
    manifest: list[dict[str, Any]] = []

    for file_path in sorted(directory.rglob("*")):
        if not file_path.is_file():
            continue

        rel = file_path.relative_to(directory)
        rel_posix = rel.as_posix()

        # Check ignore patterns against each part and the full relative path
        if _should_ignore(rel, ignore_patterns):
            continue

        content_hash = _sha256_file(file_path)
        size_bytes = file_path.stat().st_size

        manifest.append({
            "path": rel_posix,
            "content_hash": content_hash,
            "size_bytes": size_bytes,
        })

    return manifest


def load_sync_state(directory: Path) -> dict[str, Any] | None:
    """Load .toss-sync.yaml from directory, or None if it does not exist."""
    state_path = directory / SYNC_STATE_FILENAME
    if not state_path.exists():
        return None

    with open(state_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if isinstance(data, dict) else None


def save_sync_state(directory: Path, state: dict[str, Any]) -> None:
    """Write sync state to .toss-sync.yaml in the given directory."""
    state_path = directory / SYNC_STATE_FILENAME
    with open(state_path, "w", encoding="utf-8") as f:
        yaml.dump(state, f, default_flow_style=False, allow_unicode=True)
    logger.info("Sync state saved to %s", state_path)


def _should_ignore(rel_path: Path, patterns: Sequence[str]) -> bool:
    """Check if a relative path matches any ignore pattern."""
    rel_posix = rel_path.as_posix()
    for pattern in patterns:
        # Match against the full relative path
        if fnmatch(rel_posix, pattern):
            return True
        # Match against each individual path component
        for part in rel_path.parts:
            if fnmatch(part, pattern):
                return True
    return False


def _sha256_file(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
