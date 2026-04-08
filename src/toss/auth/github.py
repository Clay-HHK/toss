"""GitHub authentication: Device Flow and Personal Access Token."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


@dataclass(frozen=True)
class DeviceCodeResponse:
    """Response from GitHub device code request."""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass(frozen=True)
class AuthResult:
    """Successful authentication result."""

    jwt: str
    github_username: str
    display_name: str | None


class GitHubAuth:
    """Handle GitHub authentication against the Toss Worker API."""

    def __init__(self, api_base_url: str, timeout: int = 30) -> None:
        self._api_base = api_base_url.rstrip("/")
        self._timeout = timeout

    def authenticate_with_pat(
        self, pat: str, device_id: str | None = None
    ) -> AuthResult:
        """Authenticate using a GitHub Personal Access Token.

        Args:
            pat: GitHub personal access token.
            device_id: T1-4 device id sent to the server so the returned
                JWT is stamped with `dev` for audit / revoke.

        Returns:
            AuthResult with JWT from the Toss server.

        Raises:
            AuthError: If authentication fails.
        """
        body: dict[str, Any] = {"pat": pat}
        if device_id:
            body["device_id"] = device_id
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._api_base}/api/v1/auth/pat",
                json=body,
            )
            _check_response(resp)
            data = resp.json()

        return AuthResult(
            jwt=data["jwt"],
            github_username=data["github_username"],
            display_name=data.get("display_name"),
        )

    def start_device_flow(self) -> DeviceCodeResponse:
        """Start GitHub OAuth device flow.

        Returns:
            DeviceCodeResponse with user_code and verification_uri.

        Raises:
            AuthError: If the server rejects the request.
        """
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self._api_base}/api/v1/auth/github/device")
            _check_response(resp)
            data = resp.json()

        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data["verification_uri"],
            expires_in=data["expires_in"],
            interval=data["interval"],
        )

    def poll_device_flow(
        self,
        device_code: str,
        interval: int,
        timeout: int,
        device_id: str | None = None,
    ) -> AuthResult:
        """Poll the Toss server until the device flow completes.

        Args:
            device_code: From start_device_flow.
            interval: Seconds between polls.
            timeout: Maximum wait time in seconds.
            device_id: T1-4 device id sent to the server on the successful
                exchange so the returned JWT carries `dev`.

        Returns:
            AuthResult on success.

        Raises:
            AuthError: If polling times out or is denied.
        """
        deadline = time.monotonic() + timeout

        with httpx.Client(timeout=self._timeout) as client:
            while time.monotonic() < deadline:
                time.sleep(interval)
                body: dict[str, Any] = {"device_code": device_code}
                if device_id:
                    body["device_id"] = device_id
                resp = client.post(
                    f"{self._api_base}/api/v1/auth/github/token",
                    json=body,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return AuthResult(
                        jwt=data["jwt"],
                        github_username=data["github_username"],
                        display_name=data.get("display_name"),
                    )

                data = resp.json()
                error = data.get("error", "")

                if error == "authorization_pending":
                    continue
                if error == "slow_down":
                    interval += 5
                    continue
                if error in ("expired_token", "access_denied"):
                    raise AuthError(f"Device flow failed: {error}")

                raise AuthError(f"Unexpected error: {error}")

        raise AuthError("Device flow timed out")

    def get_user_info(self, jwt: str) -> dict[str, Any]:
        """Get current user info from the Toss server.

        Args:
            jwt: Toss JWT token.

        Returns:
            User info dict.
        """
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._api_base}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {jwt}"},
            )
            _check_response(resp)
            return resp.json()


class AuthError(Exception):
    """Authentication error."""


def _check_response(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:
            detail = resp.text
        raise AuthError(f"HTTP {resp.status_code}: {detail}")
