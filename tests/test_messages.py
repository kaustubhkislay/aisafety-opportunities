from datetime import datetime, timezone
from types import SimpleNamespace

from bot.messages import message_to_payload


def test_message_to_payload():
    message = SimpleNamespace(
        id=100,
        content="Apply: https://example.org",
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        author=SimpleNamespace(id=5),
    )

    payload = message_to_payload(message)

    assert payload == {
        "server_id": "1",
        "channel_id": "10",
        "message_id": "100",
        "author_id": "5",
        "content": "Apply: https://example.org",
        "created_at": "2026-06-25T12:00:00+00:00",
    }
