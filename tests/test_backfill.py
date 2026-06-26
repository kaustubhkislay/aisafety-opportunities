from datetime import datetime, timezone
from types import SimpleNamespace

from backend.store import RawStore
from bot.backfill import backfill_channel


def _msg(mid):
    return SimpleNamespace(
        id=mid,
        content=f"msg {mid}",
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        author=SimpleNamespace(id=5),
    )


class FakeChannel:
    def __init__(self, channel_id, messages):
        self.id = channel_id
        self._messages = messages
        self.seen_after = "unset"

    async def history(self, after=None):
        self.seen_after = after
        for m in self._messages:
            yield m


class RecordingForwarder:
    def __init__(self):
        self.forwarded = []

    async def forward(self, payload: dict) -> int:
        self.forwarded.append(payload)
        return 200


async def test_backfill_forwards_and_advances_cursor(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    channel = FakeChannel(10, [_msg(101), _msg(102)])

    count = await backfill_channel(channel, store, forwarder)

    assert count == 2
    assert [p["message_id"] for p in forwarder.forwarded] == ["101", "102"]
    assert store.get_cursor("10") == "102"  # advanced to last


async def test_backfill_passes_cursor_as_after(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.set_cursor("10", "100")
    forwarder = RecordingForwarder()
    channel = FakeChannel(10, [])

    await backfill_channel(channel, store, forwarder)

    # cursor "100" is passed through to history(after=...) as a discord.Object-like id
    assert getattr(channel.seen_after, "id", None) == 100
