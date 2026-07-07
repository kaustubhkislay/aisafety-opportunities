"""Thin async Slack Web API client.

Only the calls the adapter needs — not worth the slack_sdk dependency.
Slack signals errors with ``{"ok": false, "error": ...}`` and HTTP 200, so
``ok`` is checked on every response.
"""

import httpx

_BASE = "https://slack.com/api"


class SlackApiError(Exception):
    def __init__(self, error: str):
        super().__init__(error)
        self.error = error


class SlackWeb:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        return self._client

    @staticmethod
    def _check(data: dict) -> dict:
        if not data.get("ok"):
            raise SlackApiError(data.get("error", "unknown_error"))
        return data

    async def oauth_access(
        self, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> dict:
        resp = await self._get_client().post(
            f"{_BASE}/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        return self._check(resp.json())

    async def conversations_info(self, token: str, channel: str) -> dict:
        resp = await self._get_client().get(
            f"{_BASE}/conversations.info",
            params={"channel": channel},
            headers={"Authorization": f"Bearer {token}"},
        )
        return self._check(resp.json())

    async def conversations_history(
        self, token: str, channel: str, oldest: str, cursor: str | None = None
    ) -> dict:
        params = {"channel": channel, "oldest": oldest, "limit": "200"}
        if cursor:
            params["cursor"] = cursor
        resp = await self._get_client().get(
            f"{_BASE}/conversations.history",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        return self._check(resp.json())

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
