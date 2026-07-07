from datetime import datetime, timezone

from backend.store import RawStore
from slackbot.backfill import backfill_channel

NOW = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)


class FakeWeb:
    def __init__(self, channel: dict, pages: list[dict]):
        self._channel = channel
        self._pages = pages
        self.history_calls: list[dict] = []

    async def conversations_info(self, token, channel):
        return {"ok": True, "channel": self._channel}

    async def conversations_history(self, token, channel, oldest, cursor=None):
        self.history_calls.append({"oldest": oldest, "cursor": cursor})
        page = self._pages[len(self.history_calls) - 1]
        return page


def _store(tmp_path) -> RawStore:
    s = RawStore(str(tmp_path / "raw.db"))
    s.init_db()
    return s


def _msg(ts: str, text: str, user: str = "U1") -> dict:
    return {"type": "message", "user": user, "text": text, "ts": ts}


async def test_backfills_in_scope_channel(tmp_path):
    web = FakeWeb(
        channel={"id": "C1", "name": "ai-opportunities", "is_member": True},
        pages=[{
            "ok": True,
            "messages": [_msg("1751852400.1", "Grant: https://example.org")],
        }],
    )
    store = _store(tmp_path)
    n = await backfill_channel(web, "xoxb-1", "T1", "W", "U99", "C1", store, now=NOW)
    assert n == 1
    stored = store.get_messages()
    assert stored[0]["message_id"] == "slack:T1:C1:1751852400.1"
    # oldest = NOW - 14 days as a unix seconds string
    assert web.history_calls[0]["oldest"] == str(int(NOW.timestamp()) - 14 * 86400)


async def test_skips_wrong_name(tmp_path):
    web = FakeWeb(
        channel={"id": "C2", "name": "general", "is_member": True},
        pages=[],
    )
    n = await backfill_channel(web, "xoxb-1", "T1", "W", "U99", "C2", _store(tmp_path), now=NOW)
    assert n == 0
    assert web.history_calls == []


async def test_skips_when_not_member(tmp_path):
    web = FakeWeb(
        channel={"id": "C1", "name": "opportunities", "is_member": False},
        pages=[],
    )
    n = await backfill_channel(web, "xoxb-1", "T1", "W", "U99", "C1", _store(tmp_path), now=NOW)
    assert n == 0


async def test_excluded_and_bot_messages_not_stored(tmp_path):
    web = FakeWeb(
        channel={"id": "C1", "name": "opportunities", "is_member": True},
        pages=[{
            "ok": True,
            "messages": [
                _msg("2.0", "[private] internal only"),
                {"type": "message", "bot_id": "B1", "text": "bot noise", "ts": "3.0"},
                _msg("4.0", "Real fellowship https://example.org"),
            ],
        }],
    )
    store = _store(tmp_path)
    n = await backfill_channel(web, "xoxb-1", "T1", "W", "U99", "C1", store, now=NOW)
    assert n == 1
    assert [m["message_id"] for m in store.get_messages()] == ["slack:T1:C1:4.0"]


async def test_paginates_with_cursor(tmp_path):
    web = FakeWeb(
        channel={"id": "C1", "name": "opportunities", "is_member": True},
        pages=[
            {"ok": True,
             "messages": [_msg("1.0", "First https://example.org")],
             "response_metadata": {"next_cursor": "cur2"}},
            {"ok": True,
             "messages": [_msg("2.0", "Second https://example.org")]},
        ],
    )
    store = _store(tmp_path)
    n = await backfill_channel(web, "xoxb-1", "T1", "W", "U99", "C1", store, now=NOW)
    assert n == 2
    assert web.history_calls[1]["cursor"] == "cur2"
