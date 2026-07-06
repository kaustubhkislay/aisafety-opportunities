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


class FailingForwarder:
    def __init__(self, fail_on_index):
        self.forwarded = []
        self.fail_on_index = fail_on_index

    async def forward(self, payload: dict) -> int:
        self.forwarded.append(payload)
        return 503 if len(self.forwarded) - 1 == self.fail_on_index else 200


async def test_backfill_holds_cursor_on_forward_failure(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = FailingForwarder(fail_on_index=1)  # second message fails
    channel = FakeChannel(10, [_msg(101), _msg(102), _msg(103)])

    count = await backfill_channel(channel, store, forwarder)

    assert count == 1  # only the first forwarded successfully
    assert store.get_cursor("10") == "101"  # cursor held at last success


async def test_backfill_never_reaches_past_age_cutoff(tmp_path):
    # Channel history must start at the age cutoff even when the cursor is
    # older (or absent): items older than the window never ingest.
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.set_cursor("10", "500")  # ancient cursor, far below the cutoff

    captured = {}

    class Channel:
        id = 10

        def history(self, after=None):
            captured["after"] = after

            async def _gen():
                return
                yield  # pragma: no cover

            return _gen()

    class NoForward:
        async def forward(self, payload):
            raise AssertionError("no messages to forward")

    await backfill_channel(Channel(), store, NoForward(), oldest_snowflake=1_000_000)
    assert captured["after"].id == 1_000_000  # cutoff wins over the older cursor
