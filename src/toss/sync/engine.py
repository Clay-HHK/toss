"""Sync engine: orchestrates manifest comparison, upload, and download."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toss.client.spaces import SpaceClient
from toss.config.models import SyncConfig

from .state import compute_manifest, load_sync_state, save_sync_state

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Summary of a sync operation."""

    uploaded: int = 0
    downloaded: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)


class SyncEngine:
    """Orchestrate bi-directional sync between a local directory and a shared space."""

    def __init__(self, space_client: SpaceClient, config: SyncConfig) -> None:
        self._client = space_client
        self._config = config

    def sync(self, slug: str, local_dir: Path) -> SyncResult:
        """Run a full sync cycle for the given space and local directory.

        Args:
            slug: Space slug identifier.
            local_dir: Local directory to sync.

        Returns:
            SyncResult with counts of uploaded, downloaded, and conflicted files.
        """
        local_dir.mkdir(parents=True, exist_ok=True)
        result = SyncResult()

        # 1. Compute local manifest
        manifest = compute_manifest(local_dir, self._config.ignore_patterns)
        manifest_for_server = [
            {"path": entry["path"], "content_hash": entry["content_hash"]}
            for entry in manifest
        ]

        # 2. Ask server for sync diff
        diff = self._client.sync(slug, manifest_for_server)

        to_download: list[dict[str, Any]] = diff.get("to_download", [])
        to_upload: list[str] = diff.get("to_upload", [])
        conflicts: list[dict[str, Any]] = diff.get("conflicts", [])

        # 3. Download files from server
        for entry in to_download:
            file_path = entry["path"]
            try:
                self._client.download_file(slug, file_path, local_dir)
                result.downloaded += 1
                logger.info("Downloaded: %s", file_path)
            except Exception as exc:
                msg = f"Failed to download {file_path}: {exc}"
                logger.error(msg)
                result.errors.append(msg)

        # 4. Upload local files to server
        for file_path in to_upload:
            local_file = local_dir / file_path
            if not local_file.exists():
                msg = f"Upload skipped, file missing: {file_path}"
                logger.warning(msg)
                result.errors.append(msg)
                continue
            try:
                self._client.upload_file(slug, file_path, local_file)
                result.uploaded += 1
                logger.info("Uploaded: %s", file_path)
            except Exception as exc:
                msg = f"Failed to upload {file_path}: {exc}"
                logger.error(msg)
                result.errors.append(msg)

        # 5. Handle conflicts: download server version as filename.server.ext
        for conflict in conflicts:
            file_path = conflict["path"]
            try:
                server_dest = _conflict_path(file_path)
                self._client.download_file(slug, file_path, local_dir)
                # Rename the downloaded file to the conflict name
                downloaded = local_dir / file_path
                conflict_file = local_dir / server_dest
                if downloaded.exists():
                    conflict_file.parent.mkdir(parents=True, exist_ok=True)
                    downloaded.rename(conflict_file)
                result.conflicts += 1
                logger.warning("Conflict: %s -> saved server version as %s", file_path, server_dest)
            except Exception as exc:
                msg = f"Failed to handle conflict for {file_path}: {exc}"
                logger.error(msg)
                result.errors.append(msg)

        # 6. Save sync state
        now = datetime.now(timezone.utc).isoformat()
        state = load_sync_state(local_dir) or {}
        state["last_sync"] = now
        state["space_slug"] = slug
        save_sync_state(local_dir, state)

        return result


def _conflict_path(file_path: str) -> str:
    """Generate a conflict filename: 'dir/file.server.ext'."""
    p = Path(file_path)
    if p.suffix:
        return str(p.with_suffix(f".server{p.suffix}"))
    return f"{file_path}.server"
