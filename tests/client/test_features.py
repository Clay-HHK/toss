"""T1-7: capability probing via /api/v1/health."""

from __future__ import annotations

import httpx
import pytest
import respx

from toss.client.base import TossClient
from toss.config.models import ServerConfig


@pytest.fixture
def toss_client() -> TossClient:
    return TossClient(
        ServerConfig(base_url="https://example.test", timeout=5),
        jwt="fake-jwt",
    )


def test_fetch_features_parses_payload(toss_client: TossClient) -> None:
    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/health").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "ok",
                    "version": "0.2.0",
                    "features": ["content-sha256", "strict-headers"],
                },
            )
        )
        features = toss_client.fetch_features()

    assert "content-sha256" in features
    assert "strict-headers" in features
    assert toss_client.has_feature("content-sha256")
    assert not toss_client.has_feature("download-ticket")


def test_fetch_features_caches_result(toss_client: TossClient) -> None:
    """Second call must hit the cache, not the network."""
    with respx.mock(base_url="https://example.test") as mock:
        route = mock.get("/api/v1/health").mock(
            return_value=httpx.Response(
                200, json={"status": "ok", "features": ["x"]}
            )
        )
        toss_client.fetch_features()
        toss_client.fetch_features()
        toss_client.fetch_features()
        assert route.call_count == 1


def test_fetch_features_force_refetches(toss_client: TossClient) -> None:
    with respx.mock(base_url="https://example.test") as mock:
        route = mock.get("/api/v1/health").mock(
            return_value=httpx.Response(
                200, json={"status": "ok", "features": ["x"]}
            )
        )
        toss_client.fetch_features()
        toss_client.fetch_features(force=True)
        assert route.call_count == 2


def test_fetch_features_handles_legacy_server(toss_client: TossClient) -> None:
    """Server without `features` key should yield an empty set, not crash."""
    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/health").mock(
            return_value=httpx.Response(
                200, json={"status": "ok", "version": "0.1.0"}
            )
        )
        features = toss_client.fetch_features()

    assert features == frozenset()
    assert not toss_client.has_feature("content-sha256")


def test_fetch_features_handles_unreachable(toss_client: TossClient) -> None:
    """Connection error must yield empty set, not raise."""
    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/health").mock(side_effect=httpx.ConnectError("nope"))
        features = toss_client.fetch_features()

    assert features == frozenset()


def test_fetch_features_handles_500(toss_client: TossClient) -> None:
    with respx.mock(base_url="https://example.test") as mock:
        mock.get("/api/v1/health").mock(
            return_value=httpx.Response(500, text="boom")
        )
        features = toss_client.fetch_features()

    assert features == frozenset()
