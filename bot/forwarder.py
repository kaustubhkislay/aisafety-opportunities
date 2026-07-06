import httpx


class Forwarder:
    def __init__(self, base_url: str, secret: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # Generous read timeout: /purge deletes a server's Airtable records
            # one API call at a time, which can take minutes for a large server
            # (httpx's 5s default made the bot time out mid-purge in T6.5).
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=10.0)
            )
        return self._client

    async def forward(self, payload: dict) -> int:
        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/ingest",
            json=payload,
            headers={"X-Ingest-Secret": self.secret},
        )
        return resp.status_code

    async def retract(self, message_id: str) -> int:
        """Tell the backend to delete the record for this source message."""
        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/retract",
            json={"message_id": message_id},
            headers={"X-Ingest-Secret": self.secret},
        )
        return resp.status_code

    async def purge(self, server_id: str) -> int:
        """Tell the backend to delete all data for a server (uninstall)."""
        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/purge",
            json={"server_id": server_id},
            headers={"X-Ingest-Secret": self.secret},
        )
        return resp.status_code

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
