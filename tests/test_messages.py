from datetime import datetime, timezone
from types import SimpleNamespace

from bot.messages import message_to_payload


def test_message_to_payload():
    message = SimpleNamespace(
        id=100,
        content="Apply: https://example.org",
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1, name="AI Safety Hub"),
        channel=SimpleNamespace(id=10),
        author=SimpleNamespace(id=5),
    )

    payload = message_to_payload(message)

    assert payload == {
        "server_id": "1",
        "server_name": "AI Safety Hub",
        "channel_id": "10",
        "message_id": "100",
        "author_id": "5",
        "content": "Apply: https://example.org",
        "created_at": "2026-06-25T12:00:00+00:00",
    }


def test_forwarded_message_uses_snapshot_content():
    # Discord forwards carry empty .content; the real text lives in
    # message_snapshots (live finding: a forwarded opportunity was skipped).
    message = SimpleNamespace(
        id=200,
        content="",
        created_at=datetime(2026, 7, 6, 5, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1, name="Hub"),
        channel=SimpleNamespace(id=10),
        author=SimpleNamespace(id=5),
        message_snapshots=[SimpleNamespace(content="Fellowship open: https://x.org/apply")],
    )
    payload = message_to_payload(message)
    assert payload["content"] == "Fellowship open: https://x.org/apply"


def test_regular_message_content_wins_over_snapshots():
    message = SimpleNamespace(
        id=201,
        content="normal text",
        created_at=datetime(2026, 7, 6, 5, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1, name="Hub"),
        channel=SimpleNamespace(id=10),
        author=SimpleNamespace(id=5),
        message_snapshots=[SimpleNamespace(content="snapshot")],
    )
    assert message_to_payload(message)["content"] == "normal text"
