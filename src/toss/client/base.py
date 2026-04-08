"""Base HTTP client for the Toss API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from toss.config.manager import ConfigManager
from toss.config.models import ServerConfig

logger = logging.getLogger(__name__)

_CONNECTION_ERROR_MSG = "Connection failed. Check your network or proxy settings."


class TossAPIError(Exception):
    """Error from the Toss API."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class TossClient:
    """Synchronous HTTP client for the Toss Worker API."""

    def __init__(
        self,
        server: ServerConfig,
        jwt: str,
        device_id: str | None = None,
    ) -> None:
        self._base_url = server.base_url.rstrip("/")
        self._timeout = server.timeout
        self._headers = {
            "Authorization": f"Bearer {jwt}",
        }
        # T1-4: send the device id on every authenticated request so the
        # server can correlate audit log lines with a specific device. The
        # server already has the id embedded in the JWT payload — this
        # header is purely for logging / rate-limit scoping.
        if device_id:
            self._headers["X-Toss-Device-Id"] = device_id

    @classmethod
    def from_config(cls, cm: ConfigManager) -> TossClient:
        """Create a client from stored config and credentials.

        Raises:
            TossAPIError: If not logged in.
        """
        config = cm.load_config()
        creds = cm.load_credentials()
        jwt = creds.get("jwt")
        if not jwt:
            raise TossAPIError(401, "Not logged in. Run `toss login` first.")
        # Device id is generated lazily the first time we build a client.
        device_id = cm.load_or_create_device_id()
        return cls(config.server, jwt, device_id=device_id)

    def revoke_current_token(self) -> dict[str, Any]:
        """T1-4: blacklist the JWT we were built with.

        Returns the server payload so callers can surface whether the token
        was actually revoked or was already invalid. Silent failure would be
        a foot-gun here — if the server can't revoke, the caller should know
        before wiping local credentials.
        """
        return self.post_json("/api/v1/auth/revoke", {})

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    params=params,
                )
                return _handle_response(resp)
        except httpx.ConnectError as e:
            raise TossAPIError(0, _CONNECTION_ERROR_MSG) from e

    def post_json(
        self,
        path: str,
        data: dict[str, Any],
        params: dict[str, str] | None = None,
    ) -> Any:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    json=data,
                    params=params,
                )
                return _handle_response(resp)
        except httpx.ConnectError as e:
            raise TossAPIError(0, _CONNECTION_ERROR_MSG) from e

    def post_multipart(
        self,
        path: str,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str] | None = None,
    ) -> Any:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    files=files,
                    data=data or {},
                )
                return _handle_response(resp)
        except httpx.ConnectError as e:
            raise TossAPIError(0, _CONNECTION_ERROR_MSG) from e

    def download(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        """Download a file, returning the raw response (for streaming)."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    params=params,
                )
                if resp.status_code >= 400:
                    _raise_error(resp)
                return resp
        except httpx.ConnectError as e:
            raise TossAPIError(0, _CONNECTION_ERROR_MSG) from e

    def delete(self, path: str) -> Any:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.delete(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                )
                return _handle_response(resp)
        except httpx.ConnectError as e:
            raise TossAPIError(0, _CONNECTION_ERROR_MSG) from e

    # T1-7: capability probing.
    # Clients call `fetch_features()` once and cache the result so callers can
    # gracefully degrade against legacy servers (e.g. fall back to plaintext
    # download when the server lacks `download-ticket`). The probe never
    # raises — an unreachable or malformed server simply yields an empty set,
    # which means "use the safest defaults you support".
    _features_cache: frozenset[str] | None = None

    def fetch_features(self, *, force: bool = False) -> frozenset[str]:
        """Probe `/api/v1/health` and cache the advertised feature set.

        Args:
            force: Re-fetch even if a cached value exists.
        """
        if self._features_cache is not None and not force:
            return self._features_cache
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self._base_url}/api/v1/health")
            if resp.status_code != 200:
                self._features_cache = frozenset()
                return self._features_cache
            payload = resp.json()
            features = payload.get("features") or []
            if not isinstance(features, list):
                features = []
            self._features_cache = frozenset(str(f) for f in features)
        except (httpx.HTTPError, ValueError):
            self._features_cache = frozenset()
        return self._features_cache

    def has_feature(self, name: str) -> bool:
        """True if the server advertises `name` in its health payload."""
        return name in self.fetch_features()


def _handle_response(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        _raise_error(resp)
    return resp.json()


_STATUS_HINTS: dict[int, str] = {
    401: " (try 'toss login' to re-authenticate)",
    413: "File too large (max 50MB)",
    429: "Rate limited. Please wait a moment and try again.",
}


def _raise_error(resp: httpx.Response) -> None:
    try:
        detail = resp.json().get("error", resp.text)
    except Exception:
        detail = resp.text

    hint = _STATUS_HINTS.get(resp.status_code)
    if hint:
        if resp.status_code in (413, 429):
            detail = hint
        else:
            detail = f"{detail}{hint}"

    raise TossAPIError(resp.status_code, detail)
