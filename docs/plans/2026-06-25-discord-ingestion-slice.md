# Discord Ingestion Slice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the first working vertical slice — a thin Discord bot that forwards channel messages to an authenticated ingestion API, which writes them verbatim to a SQLite raw store, plus downtime backfill so no messages are lost across reconnects.

**Architecture:** One `uv` Python project at the repo root. `backend/` holds a FastAPI ingestion API and a `RawStore` SQLite wrapper. `bot/` holds a `discord.py` client that maps each message to a payload and POSTs it to the API via an httpx forwarder; on reconnect it backfills each channel's history since a stored per-channel cursor. The bot contains **no** classification or privacy logic yet — those are later plans. Pure logic (store, payload mapping, forwarder, backfill) is separated from Discord/HTTP glue so it is unit-testable without a live gateway.

**Tech Stack:** Python 3.12 (uv), discord.py, FastAPI, uvicorn, httpx, pydantic, SQLite (stdlib `sqlite3`), pytest + pytest-asyncio.

## Global Constraints

- Python managed via `uv` only (`uv add`, `uv run`); never raw pip/venv.
- Secrets come from environment variables only; never commit them. `.env` is gitignored; `.env.example` holds blank placeholders.
- The bot is a **thin client**: no opportunity classification, no privacy/exclusion filtering in this plan (those are later plans). It only maps messages and forwards them.
- Raw messages are stored verbatim. Dedup on `message_id` (UNIQUE) so re-forwarding (e.g. during backfill) never creates duplicates.
- The ingestion endpoint is authenticated with a shared secret sent in the `X-Ingest-Secret` header, compared against `INGEST_SHARED_SECRET`.
- Per-channel backfill uses a stored cursor (`channel_id` → last forwarded `message_id`).
- Test commands run as `uv run pytest ...` from the repo root.

---

### Task 1: uv project + raw message store

**Files:**
- Create: `pyproject.toml` (via `uv`)
- Create: `backend/__init__.py`
- Create: `backend/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RawStore(db_path: str)` with `init_db() -> None`, `insert_message(msg: dict) -> bool` (returns `True` if newly inserted, `False` if a duplicate `message_id`), and `get_messages() -> list[dict]`. A message dict has keys: `server_id`, `channel_id`, `message_id`, `author_id`, `content`, `created_at` (all `str`).

- [ ] **Step 1: Initialize the uv project and add dependencies**

Run:
```bash
cd /Users/kaustubhkislay/aisafety-opportunities
uv init --bare --python 3.12
uv add fastapi "uvicorn[standard]" httpx "discord.py" pydantic
uv add --dev pytest pytest-asyncio
```
Then append pytest async config to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_store.py`:
```python
from backend.store import RawStore

SAMPLE = {
    "server_id": "1",
    "channel_id": "10",
    "message_id": "100",
    "author_id": "5",
    "content": "Fellowship open, apply at https://example.org",
    "created_at": "2026-06-25T12:00:00+00:00",
}


def test_insert_then_read(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.insert_message(SAMPLE) is True

    rows = store.get_messages()
    assert len(rows) == 1
    assert rows[0]["message_id"] == "100"
    assert rows[0]["content"] == SAMPLE["content"]


def test_duplicate_message_id_is_ignored(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.insert_message(SAMPLE) is True
    assert store.insert_message(SAMPLE) is False  # same message_id

    assert len(store.get_messages()) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend'` (or `RawStore` undefined).

- [ ] **Step 4: Write minimal implementation**

Create `backend/__init__.py` (empty file).

Create `backend/store.py`:
```python
import sqlite3

_MESSAGE_COLUMNS = [
    "server_id",
    "channel_id",
    "message_id",
    "author_id",
    "content",
    "created_at",
]


class RawStore:
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
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE,
                    author_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def insert_message(self, msg: dict) -> bool:
        values = [msg[col] for col in _MESSAGE_COLUMNS]
        placeholders = ", ".join("?" for _ in _MESSAGE_COLUMNS)
        columns = ", ".join(_MESSAGE_COLUMNS)
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT OR IGNORE INTO messages ({columns}) VALUES ({placeholders})",
                values,
            )
            return cur.rowcount == 1

    def get_messages(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id ASC"
            ).fetchall()
            return [dict(row) for row in rows]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_store.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock backend/__init__.py backend/store.py tests/test_store.py
git commit -m "feat: raw SQLite message store with message_id dedup"
```

---

### Task 2: Per-channel cursor in the store

**Files:**
- Modify: `backend/store.py`
- Test: `tests/test_cursor.py`

**Interfaces:**
- Consumes: `RawStore` from Task 1.
- Produces: `RawStore.get_cursor(channel_id: str) -> str | None` and `RawStore.set_cursor(channel_id: str, message_id: str) -> None`. `set_cursor` upserts; `get_cursor` returns `None` for an unknown channel.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cursor.py`:
```python
from backend.store import RawStore


def test_cursor_roundtrip(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.get_cursor("10") is None

    store.set_cursor("10", "100")
    assert store.get_cursor("10") == "100"

    store.set_cursor("10", "200")  # upsert
    assert store.get_cursor("10") == "200"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cursor.py -v`
Expected: FAIL with `AttributeError: 'RawStore' object has no attribute 'get_cursor'`.

- [ ] **Step 3: Write minimal implementation**

Add the cursors table to `init_db()` in `backend/store.py` — inside the existing `with self._connect() as conn:` block in `init_db`, add a second `conn.execute(...)`:
```python
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cursors (
                    channel_id TEXT PRIMARY KEY,
                    last_message_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
```

Then add these two methods to the `RawStore` class:
```python
    def get_cursor(self, channel_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_message_id FROM cursors WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
            return row["last_message_id"] if row else None

    def set_cursor(self, channel_id: str, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cursors (channel_id, last_message_id)
                VALUES (?, ?)
                ON CONFLICT(channel_id)
                DO UPDATE SET last_message_id = excluded.last_message_id,
                              updated_at = datetime('now')
                """,
                (channel_id, message_id),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cursor.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/store.py tests/test_cursor.py
git commit -m "feat: per-channel backfill cursor in raw store"
```

---

### Task 3: Authenticated ingestion API

**Files:**
- Create: `backend/models.py`
- Create: `backend/app.py`
- Test: `tests/test_ingest_api.py`

**Interfaces:**
- Consumes: `RawStore` (Task 1).
- Produces: a FastAPI `app` with `GET /healthz` → `{"status": "ok"}` and `POST /ingest` accepting an `IngestMessage` JSON body and the `X-Ingest-Secret` header. On a valid secret it stores the message and returns `{"stored": bool, "message_id": str}` (`stored=False` if duplicate). On a bad/missing secret it returns `401`. `IngestMessage` fields: `server_id, channel_id, message_id, author_id, content, created_at` (all `str`). The store path comes from env `RAW_DB_PATH` (default `raw.db`); the secret from `INGEST_SHARED_SECRET`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_api.py`:
```python
import importlib

from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("INGEST_SHARED_SECRET", "s3cret")
    import backend.app as app_module
    importlib.reload(app_module)  # pick up patched env
    return TestClient(app_module.app)


PAYLOAD = {
    "server_id": "1",
    "channel_id": "10",
    "message_id": "100",
    "author_id": "5",
    "content": "Grant open: https://example.org",
    "created_at": "2026-06-25T12:00:00+00:00",
}
HEADERS = {"X-Ingest-Secret": "s3cret"}


def test_healthz(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ingest_stores_message(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/ingest", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {"stored": True, "message_id": "100"}

    # duplicate -> stored False
    resp2 = client.post("/ingest", json=PAYLOAD, headers=HEADERS)
    assert resp2.json() == {"stored": False, "message_id": "100"}


def test_ingest_rejects_bad_secret(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/ingest", json=PAYLOAD, headers={"X-Ingest-Secret": "wrong"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/models.py`:
```python
from pydantic import BaseModel


class IngestMessage(BaseModel):
    server_id: str
    channel_id: str
    message_id: str
    author_id: str
    content: str
    created_at: str
```

Create `backend/app.py`:
```python
import os

from fastapi import Depends, FastAPI, Header, HTTPException

from backend.models import IngestMessage
from backend.store import RawStore

app = FastAPI(title="aisafety-opportunities ingestion")

_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
_store.init_db()


def require_secret(x_ingest_secret: str | None = Header(default=None)) -> None:
    expected = os.environ.get("INGEST_SHARED_SECRET")
    if not expected or x_ingest_secret != expected:
        raise HTTPException(status_code=401, detail="invalid ingest secret")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(msg: IngestMessage, _: None = Depends(require_secret)) -> dict:
    stored = _store.insert_message(msg.model_dump())
    return {"stored": stored, "message_id": msg.message_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ingest_api.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/app.py tests/test_ingest_api.py
git commit -m "feat: authenticated /ingest API writing to raw store"
```

---

### Task 4: HTTP forwarder (bot → API)

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/forwarder.py`
- Test: `tests/test_forwarder.py`

**Interfaces:**
- Consumes: nothing (talks to the API over HTTP).
- Produces: `Forwarder(base_url: str, secret: str, client: httpx.AsyncClient | None = None)` with `async forward(payload: dict) -> int` returning the HTTP status code. It POSTs `payload` as JSON to `{base_url}/ingest` with the `X-Ingest-Secret` header. If no client is injected it creates its own.

- [ ] **Step 1: Write the failing test**

Create `tests/test_forwarder.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_forwarder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.forwarder'`.

- [ ] **Step 3: Write minimal implementation**

Create `bot/__init__.py` (empty file).

Create `bot/forwarder.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_forwarder.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add bot/__init__.py bot/forwarder.py tests/test_forwarder.py
git commit -m "feat: httpx forwarder posting messages to ingest API"
```

---

### Task 5: Message-to-payload mapping

**Files:**
- Create: `bot/messages.py`
- Test: `tests/test_messages.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `message_to_payload(message) -> dict` mapping a discord.py-style message object to the ingest payload. It reads `message.guild.id`, `message.channel.id`, `message.id`, `message.author.id`, `message.content`, and `message.created_at` (a datetime; serialized via `.isoformat()`). All ids are stringified. Output keys match `IngestMessage`: `server_id, channel_id, message_id, author_id, content, created_at`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_messages.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_messages.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.messages'`.

- [ ] **Step 3: Write minimal implementation**

Create `bot/messages.py`:
```python
def message_to_payload(message) -> dict:
    return {
        "server_id": str(message.guild.id),
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_messages.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add bot/messages.py tests/test_messages.py
git commit -m "feat: map discord message to ingest payload"
```

---

### Task 6: Backfill catch-up + Discord client wiring

**Files:**
- Create: `bot/backfill.py`
- Create: `bot/config.py`
- Create: `bot/client.py`
- Test: `tests/test_backfill.py`

**Interfaces:**
- Consumes: `message_to_payload` (Task 5), `Forwarder.forward` (Task 4), `RawStore.get_cursor`/`set_cursor` (Task 2).
- Produces: `async backfill_channel(channel, store, forwarder) -> int` — reads `channel.history(after=...)` for messages newer than the stored cursor, forwards each via `forwarder.forward(message_to_payload(m))`, advances the cursor to each forwarded `message_id`, and returns the count forwarded. `channel` must expose `id` and an async-iterator `history(after=None)`. Also produces `bot/client.py` with a `build_client()` factory wiring `on_message` and `on_ready` (backfill), and `bot/config.py` exposing `load_config()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_backfill.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backfill.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.backfill'`.

- [ ] **Step 3: Write minimal implementation**

Create `bot/backfill.py`:
```python
import discord

from bot.messages import message_to_payload


async def backfill_channel(channel, store, forwarder) -> int:
    channel_id = str(channel.id)
    last_id = store.get_cursor(channel_id)
    after = discord.Object(id=int(last_id)) if last_id else None

    count = 0
    async for message in channel.history(after=after):
        payload = message_to_payload(message)
        await forwarder.forward(payload)
        store.set_cursor(channel_id, payload["message_id"])
        count += 1
    return count
```

Create `bot/config.py`:
```python
import os


def load_config() -> dict:
    return {
        "discord_token": os.environ["DISCORD_BOT_TOKEN"],
        "ingest_base_url": os.environ.get("INGEST_BASE_URL", "http://localhost:3000"),
        "ingest_secret": os.environ["INGEST_SHARED_SECRET"],
        "raw_db_path": os.environ.get("RAW_DB_PATH", "raw.db"),
    }
```

Create `bot/client.py`:
```python
import discord

from backend.store import RawStore
from bot.backfill import backfill_channel
from bot.config import load_config
from bot.forwarder import Forwarder
from bot.messages import message_to_payload


def build_client(config: dict) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    store = RawStore(config["raw_db_path"])
    store.init_db()
    forwarder = Forwarder(config["ingest_base_url"], config["ingest_secret"])

    @client.event
    async def on_ready():
        for guild in client.guilds:
            for channel in guild.text_channels:
                try:
                    await backfill_channel(channel, store, forwarder)
                except discord.Forbidden:
                    continue  # not authorized to read this channel

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        payload = message_to_payload(message)
        await forwarder.forward(payload)
        store.set_cursor(payload["channel_id"], payload["message_id"])

    return client


def main() -> None:
    config = load_config()
    client = build_client(config)
    client.run(config["discord_token"])


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_backfill.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS (all tasks' tests green — 10 tests).

- [ ] **Step 6: Commit**

```bash
git add bot/backfill.py bot/config.py bot/client.py tests/test_backfill.py
git commit -m "feat: channel backfill and discord client wiring"
```

---

## Manual verification (after all tasks)

This slice is end-to-end testable against a real server you control:

1. Create a Discord application + bot at https://discord.com/developers, enable the **Message Content** intent, invite it to a test server.
2. Copy `.env.example` to `.env`; fill `DISCORD_BOT_TOKEN`, set `INGEST_SHARED_SECRET` to any value, `INGEST_BASE_URL=http://localhost:3000`.
3. Run the API: `uv run uvicorn backend.app:app --port 3000` (loads the same `INGEST_SHARED_SECRET` / `RAW_DB_PATH` from env).
4. In another shell, run the bot: `uv run python -m bot.client`.
5. Post a message in a channel the bot can see; confirm a row appears: `uv run python -c "from backend.store import RawStore; print(RawStore('raw.db').get_messages())"`.
6. Stop the bot, post more messages, restart it — confirm backfill picks up the messages posted while it was down (cursor advances, no duplicates).

## Out of scope for this plan (later plans)

Edge privacy/exclusion filtering, the cheap opportunity filter, PII stripping, link-safety gate, LLM extraction, dedup-with-update into Airtable, the website, RSS, email digest, OAuth install flow, retraction. This plan only proves messages flow reliably into the raw store.
