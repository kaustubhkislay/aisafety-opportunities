# Slack Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Slack as a second ingestion source: self-serve OAuth install, Events API receiver, edge exclusion, 🔒/edit retraction, uninstall purge, and 14-day backfill — all feeding the existing extraction pipeline unchanged.

**Architecture:** Per `docs/superpowers/specs/2026-07-07-slack-adapter-design.md` (Approach A): a new pure-logic `slackbot/` package plus an APIRouter in `backend/slack.py` mounted into the existing FastAPI app. Slack events land in the same `RawStore` the worker drains; no pipeline/site changes beyond a privacy-page paragraph.

**Tech Stack:** Python 3.12, FastAPI, httpx (already a dependency — no slack_sdk), SQLite on the `/data` Fly volume, pytest.

## Global Constraints

- Run tests with `uv run pytest tests/<file> -q` from the repo root.
- IDs: `server_id` = `slack:<team_id>`; `message_id` = `slack:<team_id>:<channel_id>:<ts>`.
- Bot OAuth scopes: `channels:history,channels:read,reactions:read,team:read` (public channels only).
- Reuse `bot.exclusion.should_exclude` and `bot.scope.is_ingest_channel` — do not duplicate their logic.
- Never log message content or tokens.
- New env vars: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_TOKEN_DB_PATH` (default `slack_tokens.db`), `SLACK_REDIRECT_URL`.
- Commit after each task; commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Signature verification — `slackbot/verify.py`

**Files:**
- Create: `slackbot/__init__.py` (empty)
- Create: `slackbot/verify.py`
- Test: `tests/test_slack_verify.py`

**Interfaces:**
- Produces: `verify_slack_signature(signing_secret: str, timestamp: str, body: bytes, signature: str, now: float) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_verify.py
import hashlib
import hmac

from slackbot.verify import verify_slack_signature

SECRET = "8f742231b10e8888abcd99yyyzzz85a5"
NOW = 1_751_900_000.0


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode() + b":" + body
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def test_valid_signature_accepted():
    ts = str(int(NOW))
    body = b'{"type":"url_verification"}'
    sig = _sign(SECRET, ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig, now=NOW) is True


def test_wrong_secret_rejected():
    ts = str(int(NOW))
    body = b"{}"
    sig = _sign("other-secret", ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig, now=NOW) is False


def test_tampered_body_rejected():
    ts = str(int(NOW))
    sig = _sign(SECRET, ts, b"original")
    assert verify_slack_signature(SECRET, ts, b"tampered", sig, now=NOW) is False


def test_stale_timestamp_rejected():
    ts = str(int(NOW) - 60 * 6)  # 6 minutes old: replay guard is ±5 minutes
    body = b"{}"
    sig = _sign(SECRET, ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig, now=NOW) is False


def test_garbage_timestamp_rejected():
    assert verify_slack_signature(SECRET, "not-a-number", b"{}", "v0=abc", now=NOW) is False


def test_missing_signature_rejected():
    ts = str(int(NOW))
    assert verify_slack_signature(SECRET, ts, b"{}", "", now=NOW) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_verify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'slackbot'`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/verify.py
"""Slack request verification.

Slack signs each request: ``v0=`` + HMAC-SHA256 of ``v0:<timestamp>:<body>``
with the app's signing secret. Requests older than ±5 minutes are rejected to
block replays. https://api.slack.com/authentication/verifying-requests-from-slack
"""

import hashlib
import hmac

_MAX_SKEW_SECONDS = 60 * 5


def verify_slack_signature(
    signing_secret: str, timestamp: str, body: bytes, signature: str, now: float
) -> bool:
    if not signature or not signing_secret:
        return False
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(now - ts) > _MAX_SKEW_SECONDS:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_verify.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/__init__.py slackbot/verify.py tests/test_slack_verify.py
git commit -m "feat(slack): request signature verification"
```

---

### Task 2: Identity mapping — `slackbot/ids.py`

**Files:**
- Create: `slackbot/ids.py`
- Test: `tests/test_slack_ids.py`

**Interfaces:**
- Produces:
  - `server_id(team_id: str) -> str` → `"slack:<team_id>"`
  - `message_id(team_id: str, channel_id: str, ts: str) -> str` → `"slack:<team_id>:<channel_id>:<ts>"`
  - `ts_to_iso(ts: str) -> str` → ISO-8601 UTC (`"2026-07-07T12:00:00+00:00"` style)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_ids.py
from slackbot.ids import message_id, server_id, ts_to_iso


def test_server_id_prefixed():
    assert server_id("T0123ABC") == "slack:T0123ABC"


def test_message_id_composite():
    assert (
        message_id("T0123ABC", "C0456DEF", "1751852400.000200")
        == "slack:T0123ABC:C0456DEF:1751852400.000200"
    )


def test_ts_to_iso_utc():
    # 1751852400 = 2025-07-07T01:40:00+00:00 (verified with datetime.fromtimestamp)
    assert ts_to_iso("1751852400.000200") == "2025-07-07T01:40:00+00:00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_ids.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/ids.py
"""Slack → pipeline identity mapping.

Slack ``ts`` values are unique only per channel, and must not collide with
Discord snowflakes in the shared raw store — hence the composite, prefixed ids.
"""

from datetime import datetime, timezone


def server_id(team_id: str) -> str:
    return f"slack:{team_id}"


def message_id(team_id: str, channel_id: str, ts: str) -> str:
    return f"slack:{team_id}:{channel_id}:{ts}"


def ts_to_iso(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_ids.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/ids.py tests/test_slack_ids.py
git commit -m "feat(slack): identity mapping helpers"
```

---

### Task 3: Install store — `slackbot/tokens.py`

**Files:**
- Create: `slackbot/tokens.py`
- Test: `tests/test_slack_tokens.py`

**Interfaces:**
- Produces: class `TokenStore(db_path: str)` with
  - `init_db() -> None`
  - `save(team_id: str, team_name: str, bot_token: str, bot_user_id: str) -> None` (upsert)
  - `get(team_id: str) -> dict | None` (keys: `team_id`, `team_name`, `bot_token`, `bot_user_id`)
  - `delete(team_id: str) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_tokens.py
from slackbot.tokens import TokenStore


def _store(tmp_path) -> TokenStore:
    s = TokenStore(str(tmp_path / "slack_tokens.db"))
    s.init_db()
    return s


def test_save_and_get(tmp_path):
    s = _store(tmp_path)
    s.save("T1", "AI Safety Workspace", "xoxb-abc", "U99")
    row = s.get("T1")
    assert row == {
        "team_id": "T1",
        "team_name": "AI Safety Workspace",
        "bot_token": "xoxb-abc",
        "bot_user_id": "U99",
    }


def test_get_missing_returns_none(tmp_path):
    assert _store(tmp_path).get("T404") is None


def test_save_is_upsert(tmp_path):
    s = _store(tmp_path)
    s.save("T1", "Old Name", "xoxb-old", "U99")
    s.save("T1", "New Name", "xoxb-new", "U99")
    row = s.get("T1")
    assert row["team_name"] == "New Name"
    assert row["bot_token"] == "xoxb-new"


def test_delete(tmp_path):
    s = _store(tmp_path)
    s.save("T1", "W", "xoxb-abc", "U99")
    assert s.delete("T1") is True
    assert s.get("T1") is None
    assert s.delete("T1") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_tokens.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/tokens.py
"""Per-workspace Slack install store.

Operational data (like SubscriberStore), kept in SQLite on the /data volume.
Bot tokens live only here — never in env or logs. The row is deleted on
uninstall/revocation, which is the Slack analogue of the Discord kick-purge.
"""

import sqlite3


class TokenStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS installs (
                    team_id TEXT PRIMARY KEY,
                    team_name TEXT NOT NULL DEFAULT '',
                    bot_token TEXT NOT NULL,
                    bot_user_id TEXT NOT NULL DEFAULT '',
                    installed_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def save(self, team_id: str, team_name: str, bot_token: str, bot_user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO installs (team_id, team_name, bot_token, bot_user_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    team_name = excluded.team_name,
                    bot_token = excluded.bot_token,
                    bot_user_id = excluded.bot_user_id
                """,
                (team_id, team_name, bot_token, bot_user_id),
            )

    def get(self, team_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT team_id, team_name, bot_token, bot_user_id FROM installs "
                "WHERE team_id = ?",
                (team_id,),
            ).fetchone()
            return dict(row) if row else None

    def delete(self, team_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM installs WHERE team_id = ?", (team_id,))
            return cur.rowcount == 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_tokens.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/tokens.py tests/test_slack_tokens.py
git commit -m "feat(slack): per-workspace install store"
```

---

### Task 4: Event translation — `slackbot/events.py`

**Files:**
- Create: `slackbot/events.py`
- Test: `tests/test_slack_events.py`

**Interfaces:**
- Consumes: `slackbot.ids` (`server_id`, `message_id`, `ts_to_iso`), `bot.exclusion.should_exclude`
- Produces: frozen dataclasses `Ingest(msg: dict)`, `Retract(message_id: str)`, `Backfill(channel_id: str)`, `Purge(server_id: str)`, `Drop(reason: str)` and
  `translate(event: dict, team_id: str, team_name: str, bot_user_id: str) -> Ingest | Retract | Backfill | Purge | Drop | None`
  (`event` is the inner `event` object of an `event_callback`, or the synthetic `{"type": "tokens_revoked"}` / `{"type": "app_uninstalled"}`; `Ingest.msg` matches `backend.models.IngestMessage` fields.)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_events.py
from slackbot.events import Backfill, Drop, Ingest, Purge, Retract, translate

TEAM = "T1"
NAME = "AI Safety Workspace"
BOT = "U99"


def _translate(event):
    return translate(event, team_id=TEAM, team_name=NAME, bot_user_id=BOT)


def test_plain_message_becomes_ingest():
    action = _translate({
        "type": "message",
        "channel": "C1",
        "user": "U42",
        "text": "Fellowship open, apply: https://example.org",
        "ts": "1751852400.000200",
    })
    assert isinstance(action, Ingest)
    assert action.msg == {
        "server_id": "slack:T1",
        "server_name": NAME,
        "channel_id": "C1",
        "message_id": "slack:T1:C1:1751852400.000200",
        "author_id": "U42",
        "content": "Fellowship open, apply: https://example.org",
        "created_at": "2025-07-07T01:40:00+00:00",
    }


def test_excluded_message_dropped_with_reason():
    action = _translate({
        "type": "message",
        "channel": "C1",
        "user": "U42",
        "text": "[private] internal fellowship",
        "ts": "1.0",
    })
    assert isinstance(action, Drop)
    assert action.reason == "tag:[private]"


def test_bot_message_dropped():
    action = _translate({
        "type": "message",
        "channel": "C1",
        "bot_id": "B7",
        "text": "automated post",
        "ts": "1.0",
    })
    assert isinstance(action, Drop)


def test_edit_adding_private_tag_retracts():
    action = _translate({
        "type": "message",
        "subtype": "message_changed",
        "channel": "C1",
        "message": {"text": "now [private] please", "ts": "1751852400.000200", "user": "U42"},
    })
    assert action == Retract(message_id="slack:T1:C1:1751852400.000200")


def test_edit_without_tag_ignored():
    action = _translate({
        "type": "message",
        "subtype": "message_changed",
        "channel": "C1",
        "message": {"text": "just fixing a typo", "ts": "1.0", "user": "U42"},
    })
    assert action is None


def test_other_subtype_dropped():
    action = _translate({
        "type": "message",
        "subtype": "channel_join",
        "channel": "C1",
        "ts": "1.0",
    })
    assert isinstance(action, Drop)


def test_lock_reaction_retracts():
    action = _translate({
        "type": "reaction_added",
        "reaction": "lock",
        "item": {"type": "message", "channel": "C1", "ts": "1751852400.000200"},
    })
    assert action == Retract(message_id="slack:T1:C1:1751852400.000200")


def test_other_reaction_ignored():
    action = _translate({
        "type": "reaction_added",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C1", "ts": "1.0"},
    })
    assert action is None


def test_bot_invited_triggers_backfill():
    action = _translate({
        "type": "member_joined_channel",
        "user": BOT,
        "channel": "C1",
    })
    assert action == Backfill(channel_id="C1")


def test_human_join_ignored():
    action = _translate({
        "type": "member_joined_channel",
        "user": "U42",
        "channel": "C1",
    })
    assert action is None


def test_app_uninstalled_purges():
    assert _translate({"type": "app_uninstalled"}) == Purge(server_id="slack:T1")


def test_tokens_revoked_purges():
    assert _translate({"type": "tokens_revoked"}) == Purge(server_id="slack:T1")


def test_unknown_event_ignored():
    assert _translate({"type": "team_join"}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_events.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/events.py
"""Pure translators from Slack Events API payloads to pipeline actions.

Edge exclusion runs here — an excluded message becomes ``Drop`` and is never
stored. Slack has no private-by-default channel config in v1, so the channel
default passed to ``should_exclude`` is always "public".
"""

from dataclasses import dataclass

from bot.exclusion import should_exclude
from slackbot.ids import message_id, server_id, ts_to_iso


@dataclass(frozen=True)
class Ingest:
    msg: dict


@dataclass(frozen=True)
class Retract:
    message_id: str


@dataclass(frozen=True)
class Backfill:
    channel_id: str


@dataclass(frozen=True)
class Purge:
    server_id: str


@dataclass(frozen=True)
class Drop:
    reason: str


def translate(
    event: dict, team_id: str, team_name: str, bot_user_id: str
) -> Ingest | Retract | Backfill | Purge | Drop | None:
    etype = event.get("type")

    if etype == "message":
        subtype = event.get("subtype")
        if subtype == "message_changed":
            inner = event.get("message") or {}
            excluded, reason = should_exclude(inner.get("text"), "public")
            if excluded:
                return Retract(
                    message_id=message_id(team_id, event.get("channel", ""), inner.get("ts", ""))
                )
            return None
        if subtype is not None or event.get("bot_id"):
            return Drop(reason=f"subtype:{subtype or 'bot_message'}")
        excluded, reason = should_exclude(event.get("text"), "public")
        if excluded:
            return Drop(reason=reason)
        return Ingest(
            msg={
                "server_id": server_id(team_id),
                "server_name": team_name,
                "channel_id": event.get("channel", ""),
                "message_id": message_id(team_id, event.get("channel", ""), event.get("ts", "")),
                "author_id": event.get("user", ""),
                "content": event.get("text", ""),
                "created_at": ts_to_iso(event.get("ts", "0")),
            }
        )

    if etype == "reaction_added":
        if event.get("reaction") != "lock":
            return None
        item = event.get("item") or {}
        if item.get("type") != "message":
            return None
        return Retract(
            message_id=message_id(team_id, item.get("channel", ""), item.get("ts", ""))
        )

    if etype == "member_joined_channel":
        if event.get("user") == bot_user_id:
            return Backfill(channel_id=event.get("channel", ""))
        return None

    if etype in ("app_uninstalled", "tokens_revoked"):
        return Purge(server_id=server_id(team_id))

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_events.py -q`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/events.py tests/test_slack_events.py
git commit -m "feat(slack): pure event-to-action translation with edge exclusion"
```

---

### Task 5: Slack Web API client — `slackbot/web.py`

**Files:**
- Create: `slackbot/web.py`
- Test: `tests/test_slack_web.py`

**Interfaces:**
- Produces: class `SlackWeb(client: httpx.AsyncClient | None = None)` with async methods (all return the parsed JSON `dict`; raise `SlackApiError(error: str)` when Slack replies `ok: false`):
  - `oauth_access(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict`
  - `conversations_info(token: str, channel: str) -> dict`
  - `conversations_history(token: str, channel: str, oldest: str, cursor: str | None = None) -> dict`
  - `aclose() -> None`
- Also produces: `class SlackApiError(Exception)` with attribute `error: str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_web.py
import httpx
import pytest

from slackbot.web import SlackApiError, SlackWeb


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_oauth_access_posts_form():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True, "access_token": "xoxb-1",
                                         "team": {"id": "T1", "name": "W"},
                                         "bot_user_id": "U99"})

    web = SlackWeb(client=_client(handler))
    data = await web.oauth_access("cid", "csec", "thecode", "https://x/cb")
    assert data["access_token"] == "xoxb-1"
    assert seen["url"] == "https://slack.com/api/oauth.v2.access"
    assert "code=thecode" in seen["body"]
    assert "client_id=cid" in seen["body"]


async def test_conversations_info_sends_bearer():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer xoxb-1"
        return httpx.Response(200, json={"ok": True, "channel":
                                         {"id": "C1", "name": "opportunities", "is_member": True}})

    web = SlackWeb(client=_client(handler))
    data = await web.conversations_info("xoxb-1", "C1")
    assert data["channel"]["name"] == "opportunities"


async def test_conversations_history_passes_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["channel"] == "C1"
        assert request.url.params["oldest"] == "123.000"
        assert request.url.params["cursor"] == "abc"
        return httpx.Response(200, json={"ok": True, "messages": []})

    web = SlackWeb(client=_client(handler))
    data = await web.conversations_history("xoxb-1", "C1", oldest="123.000", cursor="abc")
    assert data["messages"] == []


async def test_not_ok_raises_slack_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "channel_not_found"})

    web = SlackWeb(client=_client(handler))
    with pytest.raises(SlackApiError) as exc:
        await web.conversations_info("xoxb-1", "C404")
    assert exc.value.error == "channel_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_web.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/web.py
"""Thin async Slack Web API client.

Only the four calls the adapter needs — not worth the slack_sdk dependency.
Slack signals errors with ``{"ok": false, "error": ...}`` and HTTP 200, so
``ok`` is checked on every response.
"""

import httpx

_BASE = "https://slack.com/api"


class SlackApiError(Exception):
    def __init__(self, error: str):
        super().__init__(error)
        self.error = error


class SlackWeb:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        return self._client

    @staticmethod
    def _check(data: dict) -> dict:
        if not data.get("ok"):
            raise SlackApiError(data.get("error", "unknown_error"))
        return data

    async def oauth_access(
        self, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> dict:
        resp = await self._get_client().post(
            f"{_BASE}/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        return self._check(resp.json())

    async def conversations_info(self, token: str, channel: str) -> dict:
        resp = await self._get_client().get(
            f"{_BASE}/conversations.info",
            params={"channel": channel},
            headers={"Authorization": f"Bearer {token}"},
        )
        return self._check(resp.json())

    async def conversations_history(
        self, token: str, channel: str, oldest: str, cursor: str | None = None
    ) -> dict:
        params = {"channel": channel, "oldest": oldest, "limit": "200"}
        if cursor:
            params["cursor"] = cursor
        resp = await self._get_client().get(
            f"{_BASE}/conversations.history",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        return self._check(resp.json())

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_web.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/web.py tests/test_slack_web.py
git commit -m "feat(slack): thin async Slack Web API client"
```

---

### Task 6: Channel scope + backfill — `slackbot/backfill.py`

**Files:**
- Create: `slackbot/backfill.py`
- Test: `tests/test_slack_backfill.py`

**Interfaces:**
- Consumes: `SlackWeb.conversations_info/conversations_history` (Task 5), `slackbot.events.translate`/`Ingest` (Task 4), `bot.scope.is_ingest_channel`, `RawStore.insert_message` (existing).
- Produces: `async backfill_channel(web, token: str, team_id: str, team_name: str, bot_user_id: str, channel_id: str, store, now: datetime, max_age_days: int = 14) -> int` — returns messages ingested; returns 0 without reading history when the channel is out of scope.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_backfill.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_backfill.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/backfill.py
"""Per-channel history backfill, triggered when the bot is invited.

Scope check first (member AND name filter) so an invite to #general reads
nothing. History is paged oldest-bounded to the 14-day window and each
message goes through the same translate/exclusion path as live events.
"""

import logging
from datetime import datetime, timedelta

from bot.scope import is_ingest_channel
from slackbot.events import Ingest, translate

logger = logging.getLogger(__name__)


async def backfill_channel(
    web,
    token: str,
    team_id: str,
    team_name: str,
    bot_user_id: str,
    channel_id: str,
    store,
    now: datetime,
    max_age_days: int = 14,
) -> int:
    info = await web.conversations_info(token, channel_id)
    channel = info.get("channel") or {}
    if not channel.get("is_member") or not is_ingest_channel(channel.get("name")):
        logger.info("slack backfill skipped channel=%s (out of scope)", channel_id)
        return 0

    oldest = str(int((now - timedelta(days=max_age_days)).timestamp()))
    ingested = 0
    cursor: str | None = None
    while True:
        page = await web.conversations_history(token, channel_id, oldest=oldest, cursor=cursor)
        for raw in page.get("messages", []):
            event = dict(raw)
            event.setdefault("channel", channel_id)
            action = translate(event, team_id=team_id, team_name=team_name,
                               bot_user_id=bot_user_id)
            if isinstance(action, Ingest) and store.insert_message(action.msg):
                ingested += 1
        cursor = (page.get("response_metadata") or {}).get("next_cursor") or None
        if not cursor:
            break
    logger.info("slack backfill channel=%s ingested=%d", channel_id, ingested)
    return ingested
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_backfill.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/backfill.py tests/test_slack_backfill.py
git commit -m "feat(slack): invite-triggered 14-day channel backfill"
```

---

### Task 6a: Channel scope cache — `slackbot/channels.py`

Live `message` events carry only a channel **id**; Slack sends them for every
channel the bot is a member of, including `#general` if someone invites it
there. The consent rule is invite **and** name filter, so the events endpoint
must resolve the channel name before storing anything — cached, because it
runs on every message.

**Files:**
- Create: `slackbot/channels.py`
- Test: `tests/test_slack_channels.py`

**Interfaces:**
- Consumes: `SlackWeb.conversations_info` (Task 5), `bot.scope.is_ingest_channel`.
- Produces: class `ChannelScope()` with
  - `async in_scope(web, token: str, channel_id: str) -> bool` (cached per channel_id)
  - `invalidate(channel_id: str) -> None` (drop the cache entry — called on fresh invites so renames/re-invites re-check)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_channels.py
from slackbot.channels import ChannelScope


class FakeWeb:
    def __init__(self, channel: dict):
        self.channel = channel
        self.calls = 0

    async def conversations_info(self, token, channel):
        self.calls += 1
        return {"ok": True, "channel": self.channel}


async def test_in_scope_member_with_matching_name():
    web = FakeWeb({"id": "C1", "name": "ai-opportunities", "is_member": True})
    scope = ChannelScope()
    assert await scope.in_scope(web, "xoxb-1", "C1") is True


async def test_out_of_scope_wrong_name():
    web = FakeWeb({"id": "C2", "name": "general", "is_member": True})
    scope = ChannelScope()
    assert await scope.in_scope(web, "xoxb-1", "C2") is False


async def test_out_of_scope_not_member():
    web = FakeWeb({"id": "C3", "name": "opportunities", "is_member": False})
    scope = ChannelScope()
    assert await scope.in_scope(web, "xoxb-1", "C3") is False


async def test_result_is_cached():
    web = FakeWeb({"id": "C1", "name": "opportunities", "is_member": True})
    scope = ChannelScope()
    await scope.in_scope(web, "xoxb-1", "C1")
    await scope.in_scope(web, "xoxb-1", "C1")
    assert web.calls == 1


async def test_invalidate_forces_recheck():
    web = FakeWeb({"id": "C1", "name": "renamed-opportunities", "is_member": True})
    scope = ChannelScope()
    await scope.in_scope(web, "xoxb-1", "C1")
    scope.invalidate("C1")
    await scope.in_scope(web, "xoxb-1", "C1")
    assert web.calls == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_channels.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# slackbot/channels.py
"""Cached channel-scope check for the live event path.

Consent = the bot is a member AND the channel name passes the ingest filter.
Cached per channel id (positive and negative) because it gates every live
message; ``invalidate`` is called on fresh invites so re-invites and renames
get re-checked without a process restart.
"""

from bot.scope import is_ingest_channel


class ChannelScope:
    def __init__(self):
        self._cache: dict[str, bool] = {}

    async def in_scope(self, web, token: str, channel_id: str) -> bool:
        cached = self._cache.get(channel_id)
        if cached is None:
            info = await web.conversations_info(token, channel_id)
            channel = info.get("channel") or {}
            cached = bool(channel.get("is_member")) and is_ingest_channel(
                channel.get("name")
            )
            self._cache[channel_id] = cached
        return cached

    def invalidate(self, channel_id: str) -> None:
        self._cache.pop(channel_id, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_channels.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add slackbot/channels.py tests/test_slack_channels.py
git commit -m "feat(slack): cached channel-scope check (invite + name filter)"
```

---

### Task 7: Events endpoint — `backend/slack.py` router + mount

**Files:**
- Create: `backend/slack.py`
- Modify: `backend/app.py` (add `from backend.slack import router as slack_router` and `app.include_router(slack_router)` after the app is created)
- Test: `tests/test_slack_endpoint.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6a; existing `RawStore`, `backend.purge.purge_server`, `backend.revalidate.make_revalidator`, `get_airtable_store` pattern.
- Produces: FastAPI `router` with `POST /slack/events`; module-level `get_airtable_store()`, `_store: RawStore`, `_tokens: TokenStore`, `_web: SlackWeb`, `_scope: ChannelScope` — all monkeypatchable in tests. Task 8 adds the OAuth routes to this same module.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_endpoint.py
import hashlib
import hmac
import importlib
import json
import time

from fastapi.testclient import TestClient

SIGNING = "sig-secret"


class FakeAirtable:
    def __init__(self):
        self.deleted: list[str] = []

    def delete_by_message(self, message_id: str) -> bool:
        self.deleted.append(message_id)
        return True


class FakeScope:
    def __init__(self):
        self.result = True
        self.invalidated: list[str] = []

    async def in_scope(self, web, token, channel_id):
        return self.result

    def invalidate(self, channel_id):
        self.invalidated.append(channel_id)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("SLACK_TOKEN_DB_PATH", str(tmp_path / "slack_tokens.db"))
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "s3cret")
    import backend.slack as slack_module
    importlib.reload(slack_module)
    import backend.app as app_module
    importlib.reload(app_module)
    fake = FakeAirtable()
    monkeypatch.setattr(slack_module, "get_airtable_store", lambda: fake)
    scope = FakeScope()
    monkeypatch.setattr(slack_module, "_scope", scope)
    slack_module._tokens.save("T1", "AI Safety Workspace", "xoxb-1", "U99")
    return TestClient(app_module.app), slack_module, fake, scope


def _post(client, payload: dict, secret: str = SIGNING):
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    base = b"v0:" + ts.encode() + b":" + body
    sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )


def _event(event: dict) -> dict:
    return {"type": "event_callback", "team_id": "T1", "event": event}


def test_url_verification_challenge(tmp_path, monkeypatch):
    client, _, _, _ = _setup(tmp_path, monkeypatch)
    resp = _post(client, {"type": "url_verification", "challenge": "chal-123"})
    assert resp.status_code == 200
    assert resp.json() == {"challenge": "chal-123"}


def test_bad_signature_rejected(tmp_path, monkeypatch):
    client, _, _, _ = _setup(tmp_path, monkeypatch)
    resp = _post(client, {"type": "url_verification", "challenge": "x"}, secret="wrong")
    assert resp.status_code == 401


def test_message_event_stored(tmp_path, monkeypatch):
    client, slack_module, _, _ = _setup(tmp_path, monkeypatch)
    resp = _post(client, _event({
        "type": "message", "channel": "C1", "user": "U42",
        "text": "Grant: https://example.org", "ts": "1751852400.1",
    }))
    assert resp.status_code == 200
    stored = slack_module._store.get_messages()
    assert len(stored) == 1
    assert stored[0]["message_id"] == "slack:T1:C1:1751852400.1"
    assert stored[0]["server_name"] == "AI Safety Workspace"


def test_excluded_message_not_stored(tmp_path, monkeypatch):
    client, slack_module, _, _ = _setup(tmp_path, monkeypatch)
    _post(client, _event({
        "type": "message", "channel": "C1", "user": "U42",
        "text": "[private] hush", "ts": "2.0",
    }))
    assert slack_module._store.get_messages() == []


def test_out_of_scope_channel_not_stored(tmp_path, monkeypatch):
    # Invited to #general: membership alone is not consent — name filter gates it.
    client, slack_module, _, scope = _setup(tmp_path, monkeypatch)
    scope.result = False
    resp = _post(client, _event({
        "type": "message", "channel": "C_GENERAL", "user": "U42",
        "text": "Grant: https://example.org", "ts": "2.5",
    }))
    assert resp.status_code == 200
    assert slack_module._store.get_messages() == []


def test_unknown_team_ignored(tmp_path, monkeypatch):
    client, slack_module, _, _ = _setup(tmp_path, monkeypatch)
    resp = _post(client, {"type": "event_callback", "team_id": "T404",
                          "event": {"type": "message", "channel": "C1", "user": "U1",
                                    "text": "hi https://example.org", "ts": "3.0"}})
    assert resp.status_code == 200  # always ACK so Slack doesn't disable the app
    assert slack_module._store.get_messages() == []


def test_lock_reaction_retracts(tmp_path, monkeypatch):
    client, slack_module, fake, _ = _setup(tmp_path, monkeypatch)
    _post(client, _event({
        "type": "message", "channel": "C1", "user": "U42",
        "text": "Grant: https://example.org", "ts": "4.0",
    }))
    resp = _post(client, _event({
        "type": "reaction_added", "reaction": "lock",
        "item": {"type": "message", "channel": "C1", "ts": "4.0"},
    }))
    assert resp.status_code == 200
    assert fake.deleted == ["slack:T1:C1:4.0"]
    # tombstoned so the worker never extracts it
    msgs = slack_module._store.get_messages()
    assert msgs[0]["processed_at"] is not None


def test_app_uninstalled_purges_and_deletes_token(tmp_path, monkeypatch):
    client, slack_module, _, _ = _setup(tmp_path, monkeypatch)
    _post(client, _event({
        "type": "message", "channel": "C1", "user": "U42",
        "text": "Grant: https://example.org", "ts": "5.0",
    }))
    resp = _post(client, _event({"type": "app_uninstalled"}))
    assert resp.status_code == 200
    assert slack_module._store.get_messages_by_server("slack:T1") == []
    assert slack_module._tokens.get("T1") is None


def test_bot_invite_triggers_backfill(tmp_path, monkeypatch):
    client, slack_module, _, scope = _setup(tmp_path, monkeypatch)
    calls = {}

    async def fake_backfill(web, token, team_id, team_name, bot_user_id,
                            channel_id, store, now, max_age_days=14):
        calls["channel"] = channel_id
        calls["token"] = token
        return 3

    monkeypatch.setattr(slack_module, "backfill_channel", fake_backfill)
    resp = _post(client, _event({
        "type": "member_joined_channel", "user": "U99", "channel": "C7",
    }))
    assert resp.status_code == 200
    assert calls == {"channel": "C7", "token": "xoxb-1"}
    # fresh invite must invalidate any stale negative scope cache for the channel
    assert scope.invalidated == ["C7"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_endpoint.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.slack'`

- [ ] **Step 3: Write the implementation**

```python
# backend/slack.py
"""Slack ingestion routes (Events API + OAuth), mounted into backend.app.

Design: docs/superpowers/specs/2026-07-07-slack-adapter-design.md. Slack
pushes events here; exclusion runs in slackbot.events.translate before
anything is stored. Every verified event is ACKed 200 (even when ignored)
so Slack does not auto-disable the app; signature failures get 401.
"""

import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from backend.purge import purge_server
from backend.revalidate import make_revalidator
from backend.store import RawStore
from slackbot.backfill import backfill_channel
from slackbot.channels import ChannelScope
from slackbot.events import Backfill, Drop, Ingest, Purge, Retract, translate
from slackbot.tokens import TokenStore
from slackbot.verify import verify_slack_signature
from slackbot.web import SlackWeb

logger = logging.getLogger(__name__)

router = APIRouter()

_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
_store.init_db()

_tokens = TokenStore(os.environ.get("SLACK_TOKEN_DB_PATH", "slack_tokens.db"))
_tokens.init_db()

_web = SlackWeb()

_scope = ChannelScope()

_revalidator = make_revalidator(os.environ)


def _ping_site() -> None:
    if _revalidator is not None:
        _revalidator()


def get_airtable_store():
    # Lazy, mirroring backend.app: importable without Airtable env; overridden in tests.
    from backend.airtable import AirtableStore, backend_from_env

    return AirtableStore(backend_from_env())


async def _run_backfill(token: str, team_id: str, team_name: str,
                        bot_user_id: str, channel_id: str) -> None:
    try:
        await backfill_channel(
            _web, token, team_id, team_name, bot_user_id, channel_id,
            _store, now=datetime.now(timezone.utc),
        )
    except Exception:
        logger.exception("slack backfill failed channel=%s", channel_id)


@router.post("/slack/events")
async def slack_events(request: Request, background: BackgroundTasks) -> dict:
    body = await request.body()
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not verify_slack_signature(
        secret,
        request.headers.get("x-slack-request-timestamp", ""),
        body,
        request.headers.get("x-slack-signature", ""),
        now=time.time(),
    ):
        raise HTTPException(status_code=401, detail="bad slack signature")

    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}
    if payload.get("type") != "event_callback":
        return {"ok": True}

    team_id = payload.get("team_id", "")
    install = _tokens.get(team_id)
    event = payload.get("event") or {}
    if install is None:
        # Uninstalled/unknown workspace: nothing to do, but still ACK.
        logger.info("slack event from unknown team=%s type=%s", team_id, event.get("type"))
        return {"ok": True}

    action = translate(event, team_id=team_id, team_name=install["team_name"],
                       bot_user_id=install["bot_user_id"])

    if isinstance(action, Ingest):
        # Membership alone is not consent: the name filter gates the live path
        # exactly like backfill (invited AND name contains "opportunities").
        if await _scope.in_scope(_web, install["bot_token"], action.msg["channel_id"]):
            _store.insert_message(action.msg)
        else:
            logger.info("slack drop team=%s reason=out-of-scope channel=%s",
                        team_id, action.msg["channel_id"])
    elif isinstance(action, Retract):
        airtable = get_airtable_store()
        deleted = airtable.delete_by_message(action.message_id)
        _store.mark_processed(action.message_id)
        if deleted:
            _ping_site()
    elif isinstance(action, Purge):
        airtable = get_airtable_store()
        counts = purge_server(airtable, _store, action.server_id)
        _tokens.delete(team_id)
        if counts.get("airtable"):
            _ping_site()
        logger.info("slack purge team=%s counts=%s", team_id, counts)
    elif isinstance(action, Backfill):
        _scope.invalidate(action.channel_id)  # fresh invite: re-check name/membership
        background.add_task(_run_backfill, install["bot_token"], team_id,
                            install["team_name"], install["bot_user_id"],
                            action.channel_id)
    elif isinstance(action, Drop):
        logger.info("slack drop team=%s reason=%s", team_id, action.reason)

    return {"ok": True}
```

Note: this module intentionally mirrors `backend.app`'s module-singleton
pattern so `importlib.reload` in tests picks up patched env. `get_airtable_store()`
is called directly (not via `Depends`), so tests replace it with
`monkeypatch.setattr(slack_module, "get_airtable_store", lambda: fake)` — the
`_setup` helper above already does this.

Then in `backend/app.py`, after `app = FastAPI(...)` add:

```python
from backend.slack import router as slack_router

app.include_router(slack_router)
```

(Place the import at the top of the file with the other imports; module-level
side effects are identical to `backend.app`'s own store init.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_endpoint.py -q`
Expected: 9 passed. Also run the full suite (`uv run pytest -q`) — existing
`test_ingest_api.py` must still pass with the router mounted.

- [ ] **Step 5: Commit**

```bash
git add backend/slack.py backend/app.py tests/test_slack_endpoint.py
git commit -m "feat(slack): Events API endpoint with dispatch to store/retract/purge/backfill"
```

---

### Task 8: OAuth install flow — `/slack/install` + `/slack/oauth/callback`

**Files:**
- Modify: `backend/slack.py` (add two routes)
- Test: `tests/test_slack_oauth.py`

**Interfaces:**
- Consumes: `SlackWeb.oauth_access` (Task 5), `TokenStore.save` (Task 3).
- Produces: `GET /slack/install` (302 to Slack consent) and `GET /slack/oauth/callback?code=...` (HTML confirmation). Env consumed: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_REDIRECT_URL`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slack_oauth.py
import importlib
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("SLACK_TOKEN_DB_PATH", str(tmp_path / "slack_tokens.db"))
    monkeypatch.setenv("SLACK_CLIENT_ID", "cid.123")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
    monkeypatch.setenv("SLACK_REDIRECT_URL", "https://api.example.org/slack/oauth/callback")
    import backend.slack as slack_module
    importlib.reload(slack_module)
    import backend.app as app_module
    importlib.reload(app_module)
    return TestClient(app_module.app, follow_redirects=False), slack_module


def test_install_redirects_to_slack_consent(tmp_path, monkeypatch):
    client, _ = _setup(tmp_path, monkeypatch)
    resp = client.get("/slack/install")
    assert resp.status_code == 307 or resp.status_code == 302
    url = urlparse(resp.headers["location"])
    assert url.netloc == "slack.com"
    assert url.path == "/oauth/v2/authorize"
    q = parse_qs(url.query)
    assert q["client_id"] == ["cid.123"]
    assert q["scope"] == ["channels:history,channels:read,reactions:read,team:read"]
    assert q["redirect_uri"] == ["https://api.example.org/slack/oauth/callback"]


def test_callback_exchanges_code_and_saves_install(tmp_path, monkeypatch):
    client, slack_module = _setup(tmp_path, monkeypatch)
    seen = {}

    async def fake_oauth_access(client_id, client_secret, code, redirect_uri):
        seen.update(code=code, client_id=client_id)
        return {"ok": True, "access_token": "xoxb-new",
                "team": {"id": "T9", "name": "New Workspace"},
                "bot_user_id": "U77"}

    monkeypatch.setattr(slack_module._web, "oauth_access", fake_oauth_access)
    resp = client.get("/slack/oauth/callback?code=thecode")
    assert resp.status_code == 200
    assert "invite" in resp.text.lower()  # tells the admin the next step
    assert seen["code"] == "thecode"
    assert slack_module._tokens.get("T9") == {
        "team_id": "T9", "team_name": "New Workspace",
        "bot_token": "xoxb-new", "bot_user_id": "U77",
    }


def test_callback_without_code_is_400(tmp_path, monkeypatch):
    client, _ = _setup(tmp_path, monkeypatch)
    resp = client.get("/slack/oauth/callback")
    assert resp.status_code == 400


def test_callback_oauth_error_is_502(tmp_path, monkeypatch):
    client, slack_module = _setup(tmp_path, monkeypatch)

    async def failing_oauth_access(client_id, client_secret, code, redirect_uri):
        from slackbot.web import SlackApiError
        raise SlackApiError("invalid_code")

    monkeypatch.setattr(slack_module._web, "oauth_access", failing_oauth_access)
    resp = client.get("/slack/oauth/callback?code=bad")
    assert resp.status_code == 502
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack_oauth.py -q`
Expected: FAIL — 404s (routes don't exist yet)

- [ ] **Step 3: Add the routes to `backend/slack.py`**

Append (plus `RedirectResponse`/`HTMLResponse` imports from
`fastapi.responses`, and `SlackApiError` from `slackbot.web`):

```python
_SCOPES = "channels:history,channels:read,reactions:read,team:read"


@router.get("/slack/install")
def slack_install():
    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    redirect = os.environ.get("SLACK_REDIRECT_URL", "")
    url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}&scope={_SCOPES}&redirect_uri={redirect}"
    )
    return RedirectResponse(url)


@router.get("/slack/oauth/callback", response_class=HTMLResponse)
async def slack_oauth_callback(code: str | None = None) -> HTMLResponse:
    if not code:
        return HTMLResponse("<p>Missing OAuth code.</p>", status_code=400)
    try:
        data = await _web.oauth_access(
            os.environ.get("SLACK_CLIENT_ID", ""),
            os.environ.get("SLACK_CLIENT_SECRET", ""),
            code,
            os.environ.get("SLACK_REDIRECT_URL", ""),
        )
    except SlackApiError as exc:
        logger.warning("slack oauth exchange failed: %s", exc.error)
        return HTMLResponse(f"<p>Slack install failed: {exc.error}</p>", status_code=502)
    team = data.get("team") or {}
    _tokens.save(
        team.get("id", ""),
        team.get("name", ""),
        data.get("access_token", ""),
        data.get("bot_user_id", ""),
    )
    logger.info("slack installed team=%s", team.get("id"))
    return HTMLResponse(
        "<h1>Installed!</h1>"
        "<p>Now <code>/invite</code> the bot into your opportunities channel "
        "(its name must contain “opportunities”). The last 14 days backfill "
        "automatically, and new posts appear on the board within seconds.</p>"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack_oauth.py -q`
Expected: 4 passed. Then the full backend suite: `uv run pytest -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/slack.py tests/test_slack_oauth.py
git commit -m "feat(slack): self-serve OAuth install flow"
```

---

### Task 9: Docs, env template, and privacy wording

**Files:**
- Modify: `README.md` (Slack install section + status line + diagram caption)
- Modify: `.env.example` (new Slack vars, documented inline like the others)
- Modify: `web/app/privacy/page.tsx` (Slack ingestion wording)
- Test: `web/legal-pages.test.tsx` already asserts privacy content renders — run the web suite after editing.

**Interfaces:** none (documentation only).

- [ ] **Step 1: Add Slack vars to `.env.example`**

Append:

```bash
# --- Slack adapter (optional; leave blank to run Discord-only) ---
# From your Slack app's Basic Information page (create one at api.slack.com/apps
# with bot scopes channels:history,channels:read,reactions:read,team:read and
# event subscriptions message.channels, reaction_added, member_joined_channel,
# app_uninstalled, tokens_revoked pointed at <backend>/slack/events).
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=
# Public URL of the OAuth callback, e.g. https://<your-backend>/slack/oauth/callback
SLACK_REDIRECT_URL=
# SQLite file for per-workspace bot tokens (on the Fly volume in production)
SLACK_TOKEN_DB_PATH=slack_tokens.db
```

- [ ] **Step 2: README — add a Slack install subsection**

After the Discord install section, add:

```markdown
## Install the bot in your Slack workspace

1. **Click the install link:** `https://<backend-host>/slack/install` and
   authorize — the app asks only for read scopes on public channels.
2. **`/invite` the bot** into your opportunities channel (name must contain
   `opportunities`). Inviting it to any other channel does nothing.
3. **That's it** — the last 14 days backfill and new posts appear on the site
   within seconds. `[private]`-style tags, 🔒-reaction retraction, and
   uninstall purge work exactly as on Discord, with one honest difference:
   Slack pushes events to our backend, so excluded messages are discarded at
   ingestion (before storage or processing) rather than inside your workspace.
```

Update the Status section's "Slack support is a later adapter" sentence to
say Slack ingestion is live/beta.

- [ ] **Step 3: Privacy page — add the Slack paragraph**

In `web/app/privacy/page.tsx`, inside the "What we collect" section after the
Discord edge-exclusion paragraph, add:

```tsx
<p className="mt-2">
  <strong>Slack:</strong> the bot reads only public channels it is explicitly
  invited to whose names contain <code>opportunities</code>. Slack delivers
  events to our backend, so exclusion-tagged messages are discarded at
  ingestion — before storage or processing — rather than inside your
  workspace. Retraction (🔒 or a <code>[private]</code> edit) and
  uninstall purge work the same as on Discord.
</p>
```

- [ ] **Step 4: Run both suites**

Run: `uv run pytest -q` (repo root) — all pass.
Run: `cd web && npm test` — all pass (legal-pages test still green).
Run: `cd web && npm run build` — compiles.

- [ ] **Step 5: Commit**

```bash
git add README.md .env.example web/app/privacy/page.tsx
git commit -m "docs(slack): install instructions, env template, privacy wording"
```

---

### Post-implementation (manual, owner-only — not part of this plan)

Creating the actual Slack app at api.slack.com/apps, setting the five Fly
secrets, and pointing Event Subscriptions at the production `/slack/events`
URL require the owner's Slack/Fly credentials. The code ships inert without
them (Slack routes 401/no-op when env is blank).
