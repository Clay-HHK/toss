"""T1-4: device id persistence + device-bound JWT / revoke client flow."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from toss.client.base import TossAPIError, TossClient
from toss.config.manager import ConfigManager
from toss.config.models import ServerConfig


def test_device_id_is_generated_and_stable(tmp_path: Path) -> None:
    cm = ConfigManager(base_dir=str(tmp_path))
    first = cm.load_or_create_device_id()
    second = cm.load_or_create_device_id()
    assert first == second
    assert len(first) == 32  # UUID4 hex


def test_device_id_file_is_readable(tmp_path: Path) -> None:
    cm = ConfigManager(base_dir=str(tmp_path))
    device_id = cm.load_or_create_device_id()
    on_disk = (tmp_path / "device_id").read_text(encoding="utf-8").strip()
    assert on_disk == device_id


def test_client_sends_device_id_header(tmp_path: Path) -> None:
    cm = ConfigManager(base_dir=str(tmp_path))
    device_id = cm.load_or_create_device_id()

    client = TossClient(
        ServerConfig(base_url="https://example.test", timeout=5),
        jwt="fake-jwt",
        device_id=device_id,
    )

    with respx.mock(base_url="https://example.test") as mock:
        route = mock.get("/api/v1/auth/me").mock(
            return_value=httpx.Response(200, json={"id": "u1"})
        )
        client.get("/api/v1/auth/me")

        sent = route.calls[0].request
        assert sent.headers.get("X-Toss-Device-Id") == device_id


def test_revoke_current_token_calls_endpoint() -> None:
    client = TossClient(
        ServerConfig(base_url="https://example.test", timeout=5),
        jwt="fake-jwt",
    )
    with respx.mock(base_url="https://example.test") as mock:
        route = mock.post("/api/v1/auth/revoke").mock(
            return_value=httpx.Response(
                200, json={"revoked": True, "jti": "abc-123"}
            )
        )
        result = client.revoke_current_token()

        assert route.called
        assert result == {"revoked": True, "jti": "abc-123"}


def test_clear_credentials_removes_profile_entry(tmp_path: Path) -> None:
    cm = ConfigManager(base_dir=str(tmp_path))
    cm.ensure_dirs()
    cm.add_profile("default", "https://example.test")
    cm.save_credentials({"jwt": "fake", "github_username": "alice"})
    assert cm.load_credentials() == {"jwt": "fake", "github_username": "alice"}

    cm.clear_credentials()
    assert cm.load_credentials() == {}


def test_clear_credentials_noop_when_missing(tmp_path: Path) -> None:
    cm = ConfigManager(base_dir=str(tmp_path))
    # No credentials file — should not raise.
    cm.clear_credentials()
