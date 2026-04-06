"""Base HTTP client for the Toss API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from toss.config.manager import ConfigManager
from toss.config.models import ServerConfig

logger = logging.getLogger(__name__)


class TossAPIError(Exception):
    """Error from the Toss API."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class TossClient:
    """Synchronous HTTP client for the Toss Worker API."""

    def __init__(self, server: ServerConfig, jwt: str) -> None:
        self._base_url = server.base_url.rstrip("/")
        self._timeout = server.timeout
        self._headers = {
            "Authorization": f"Bearer {jwt}",
        }

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
        return cls(config.server, jwt)

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base_url}{path}",
                headers=self._headers,
                params=params,
            )
            return _handle_response(resp)

    def post_json(self, path: str, data: dict[str, Any]) -> Any:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}{path}",
                headers=self._headers,
                json=data,
            )
            return _handle_response(resp)

    def post_multipart(
        self,
        path: str,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str] | None = None,
    ) -> Any:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}{path}",
                headers=self._headers,
                files=files,
                data=data or {},
            )
            return _handle_response(resp)

    def download(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        """Download a file, returning the raw response (for streaming)."""
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base_url}{path}",
                headers=self._headers,
                params=params,
            )
            if resp.status_code >= 400:
                _raise_error(resp)
            return resp

    def delete(self, path: str) -> Any:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.delete(
                f"{self._base_url}{path}",
                headers=self._headers,
            )
            return _handle_response(resp)


def _handle_response(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        _raise_error(resp)
    return resp.json()


def _raise_error(resp: httpx.Response) -> None:
    try:
        detail = resp.json().get("error", resp.text)
    except Exception:
        detail = resp.text
    raise TossAPIError(resp.status_code, detail)
