import httpx

from bot.forwarder import Forwarder

PAYLOAD = {
    "server_id": "1",
    "channel_id": "10",
    "message_id": "100",
    "author_id": "5",
    "content": "hi",
    "created_at": "2026-06-25T12:00:00+00:00",
}


async def test_forward_posts_with_secret_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen["url"] = str(request.url)
        seen["secret"] = request.headers.get("x-ingest-secret")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"stored": True, "message_id": "100"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    forwarder = Forwarder("http://api.local", "s3cret", client=client)

    status = await forwarder.forward(PAYLOAD)

    assert status == 200
    assert seen["url"] == "http://api.local/ingest"
    assert seen["secret"] == "s3cret"
    assert seen["body"]["message_id"] == "100"
    await client.aclose()
