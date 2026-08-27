# github/app_auth.py — GitHub App JWT signing + installation-token exchange
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import httpx
import jwt

from ..core.config import TransportConfig
from ..core.transport import build_client

_JWT_IAT_BACKDATE = 60
_JWT_TTL = 540  # 9 minutes — under GitHub's 10-minute hard cap
_TOKEN_REFRESH_MARGIN = timedelta(minutes=5)


class GithubAppAuth(httpx.Auth):
    """`httpx.Auth` that authenticates as a GitHub App installation.

    Signs a short-lived RS256 JWT to exchange for an installation access
    token, caching the token and proactively refreshing it before expiry
    (and reactively on a 401, in case of clock skew or early revocation)."""

    def __init__(
        self,
        app_id: str,
        installation_id: str,
        private_key: str,
        base_url: str,
        transport: TransportConfig,
        *,
        token_client: httpx.Client | None = None,
    ) -> None:
        self._app_id = app_id
        self._installation_id = installation_id
        self._private_key = private_key
        self._base_url = base_url
        self._transport = transport
        # Overridable for tests, which need the token exchange to hit the
        # same MockTransport as the outer client instead of the network.
        self._token_client = token_client
        self._token: str | None = None
        self._expires_at: datetime | None = None

    def _generate_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - _JWT_IAT_BACKDATE,
            "exp": now + _JWT_TTL,
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def _fetch_installation_token(self) -> None:
        client = self._token_client or build_client(
            base_url=self._base_url, transport=self._transport
        )
        try:
            resp = client.post(
                f"/app/installations/{self._installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {self._generate_jwt()}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
        finally:
            if self._token_client is None:
                client.close()
        body = resp.json()
        self._token = body["token"]
        expires_at = body["expires_at"].replace("Z", "+00:00")
        self._expires_at = datetime.fromisoformat(expires_at)

    def _needs_refresh(self) -> bool:
        if self._token is None or self._expires_at is None:
            return True
        return datetime.now(UTC) >= self._expires_at - _TOKEN_REFRESH_MARGIN

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        if self._needs_refresh():
            self._fetch_installation_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request

        if response.status_code == 401:
            self._fetch_installation_token()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request
