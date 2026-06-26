import httpx


class Forwarder:
    def __init__(self, base_url: str, secret: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def forward(self, payload: dict) -> int:
        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/ingest",
            json=payload,
            headers={"X-Ingest-Secret": self.secret},
        )
        return resp.status_code
