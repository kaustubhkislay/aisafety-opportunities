from datetime import datetime, timezone
from types import SimpleNamespace

from backend.store import RawStore
from bot.coordinator import Ingestor


def _msg(mid, channel_id):
    return SimpleNamespace(
        id=mid,
        content=f"msg {mid}",
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=channel_id),
        author=SimpleNamespace(id=5),
    )


class FilteringChannel:
    """Fake channel whose history() respects the `after` snowflake like
    discord.py, so a cursor advanced past history actually hides it."""

    def __init__(self, channel_id, messages):
        self.id = channel_id
        self._messages = messages

    async def history(self, after=None):
        after_id = after.id if after is not None else 0
        for m in self._messages:
            if m.id > after_id:
                yield m


class RecordingForwarder:
    def __init__(self):
        self.forwarded = []

    async def forward(self, payload: dict) -> int:
        self.forwarded.append(payload)
        return 200


async def test_live_message_during_backfill_does_not_skip_downtime_history(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    ingestor = Ingestor(store, forwarder)

    # A live message arrives in channel 20 BEFORE backfill reaches that channel.
    live = _msg(305, channel_id=20)
    await ingestor.handle_live(live)

    assert forwarder.forwarded == []  # buffered, not forwarded during backfill
    assert store.get_cursor("20") is None  # cursor NOT advanced by buffered live msg

    # Channel 20 has downtime history (201, 202) with ids < the live 305.
    channel20 = FilteringChannel(20, [_msg(201, 20), _msg(202, 20)])
    await ingestor.run_startup([channel20])

    forwarded_ids = [p["message_id"] for p in forwarder.forwarded]
    assert "201" in forwarded_ids  # downtime history NOT skipped
    assert "202" in forwarded_ids
    assert "305" in forwarded_ids  # buffered live message drained after backfill


async def test_messages_after_ready_forward_immediately(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    ingestor = Ingestor(store, forwarder)

    await ingestor.run_startup([])  # no channels -> becomes ready immediately

    await ingestor.handle_live(_msg(400, channel_id=20))
    assert [p["message_id"] for p in forwarder.forwarded] == ["400"]
    assert store.get_cursor("20") == "400"
