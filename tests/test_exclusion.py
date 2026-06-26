from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.store import RawStore
from bot.backfill import backfill_channel
from bot.coordinator import Ingestor
from bot.exclusion import should_exclude


# --- pure function -------------------------------------------------------

@pytest.mark.parametrize("tag", ["[private]", "school-specific", "internal", "do-not-share"])
def test_each_tag_excludes(tag):
    excluded, reason = should_exclude(f"Great fellowship {tag} for members", "public")
    assert excluded is True
    assert tag in reason


def test_tag_match_is_case_insensitive():
    excluded, _ = should_exclude("This channel is INTERNAL only", "public")
    assert excluded is True


def test_tag_match_respects_word_boundaries():
    # "internal" must not fire on "international"
    excluded, reason = should_exclude("International AI fellowship, apply now", "public")
    assert excluded is False
    assert reason == "ok"


def test_clean_public_message_not_excluded():
    excluded, reason = should_exclude("Apply to our fellowship https://x.org/apply", "public")
    assert excluded is False
    assert reason == "ok"


def test_private_default_channel_excludes_untagged_message():
    excluded, reason = should_exclude("a perfectly normal announcement", "private")
    assert excluded is True
    assert reason == "private-channel"


def test_empty_content_in_public_channel_is_not_excluded():
    assert should_exclude("", "public") == (False, "ok")


# --- integration: privacy invariant (no transmit on exclude) -------------

def _msg(mid, channel_id, content):
    return SimpleNamespace(
        id=mid,
        content=content,
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=channel_id),
        author=SimpleNamespace(id=5),
    )


class RecordingForwarder:
    def __init__(self):
        self.forwarded = []

    async def forward(self, payload: dict) -> int:
        self.forwarded.append(payload)
        return 200


class FilteringChannel:
    def __init__(self, channel_id, messages):
        self.id = channel_id
        self._messages = messages

    async def history(self, after=None):
        after_id = after.id if after is not None else 0
        for m in self._messages:
            if m.id > after_id:
                yield m


async def test_live_excluded_message_is_not_transmitted(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    ingestor = Ingestor(store, forwarder)
    await ingestor.run_startup([])  # ready

    await ingestor.handle_live(_msg(500, 20, "members only [private] do not post"))

    assert forwarder.forwarded == []  # never left the bot
    assert store.get_cursor("20") is None  # cursor not advanced for a dropped msg


async def test_live_clean_message_is_transmitted(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    ingestor = Ingestor(store, forwarder)
    await ingestor.run_startup([])

    await ingestor.handle_live(_msg(501, 20, "Apply: https://x.org fellowship"))

    assert [p["message_id"] for p in forwarder.forwarded] == ["501"]


async def test_backfill_drops_excluded_and_keeps_clean(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    channel = FilteringChannel(30, [
        _msg(601, 30, "[private] internal note"),
        _msg(602, 30, "Open call: apply https://y.org"),
    ])

    await backfill_channel(channel, store, forwarder)

    ids = [p["message_id"] for p in forwarder.forwarded]
    assert "601" not in ids  # excluded, never transmitted
    assert "602" in ids
    assert store.get_cursor("30") == "602"  # cursor advanced past both


async def test_backfill_private_default_channel_transmits_nothing(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    forwarder = RecordingForwarder()
    channel = FilteringChannel(31, [_msg(701, 31, "Open call: apply https://y.org")])

    await backfill_channel(channel, store, forwarder, channel_default="private")

    assert forwarder.forwarded == []
