# Extraction Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A background worker that turns raw Discord messages (Slice 1's `RawStore`) into structured, deduped opportunity records in Airtable: keyword pre-filter → hosted open-weights LLM extraction (classify + extract + PII-normalize) → rule-based link-safety → key-based dedup-with-update → Airtable upsert.

**Architecture:** Same `uv` Python project as Slice 1. The worker polls the raw store for unprocessed rows and runs each through a pipeline of small, pure-where-possible units. The LLM call goes through an OpenAI-compatible client (Qwen/Kimi via OpenRouter/Together/Moonshot/…), not the Anthropic SDK. Deterministic stages (filter, link-safety, dedup, field-mapping) are plain Python with no LLM. Network clients (OpenAI-compatible, Airtable) are injected so every unit is tested without network.

**Tech Stack:** Python 3.12 (uv), pydantic, `openai` (OpenAI-compatible client), `pyairtable`, SQLite (stdlib), pytest. Slice 1 already provides `RawStore`, `backend/models.py`, the pytest setup, and `.env`/`.env.example`.

## Global Constraints

- Python managed via `uv` only (`uv add`, `uv run`); never raw pip/venv.
- Secrets from environment only; never committed. `.env` is gitignored; `.env.example` holds blank placeholders.
- Extraction LLM is a **hosted open-weights model via an OpenAI-compatible client** — `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` from env. NOT the Anthropic SDK.
- Deterministic stages (filter, link-safety, dedup, field-mapping) are pure Python — no LLM, no network.
- `type` vocabulary is fixed: `job, internship, fellowship, grant, event, course, reading-group, other`. Unknown values coerce to `other`.
- Airtable upsert is keyed on the `dedup_key` field. Base/table: `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`, `AIRTABLE_API_KEY` from env (base `appSnlPD0tE1MWWZ2`, table `Opportunities` already created).
- On any pipeline failure (LLM error, Airtable error), the raw row is left unprocessed so it retries next loop. No message is silently dropped: every row is either marked processed (filtered, not-an-opportunity, withheld, or published) or left for retry.
- Test commands run as `uv run pytest ...` from the repo root.

---

### Task 1: RawStore `processed_at` marker

**Files:**
- Modify: `backend/store.py` (extend `init_db`; add `claim_unprocessed`, `mark_processed`)
- Test: `tests/test_processed.py`

**Interfaces:**
- Consumes: `RawStore(db_path)` with `init_db()` and `insert_message(msg: dict) -> bool` (Slice 1).
- Produces: `RawStore.claim_unprocessed(limit: int) -> list[dict]` (rows where `processed_at IS NULL`, oldest first, capped at `limit`) and `RawStore.mark_processed(message_id: str) -> None` (sets `processed_at` to now). The migration adds a nullable `processed_at` column to `messages` idempotently in `init_db()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_processed.py`:
```python
from backend.store import RawStore


def _msg(mid):
    return {
        "server_id": "1",
        "channel_id": "10",
        "message_id": mid,
        "author_id": "5",
        "content": f"content {mid}",
        "created_at": "2026-06-25T12:00:00+00:00",
    }


def test_claim_and_mark_processed(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.insert_message(_msg("100"))
    store.insert_message(_msg("101"))

    claimed = store.claim_unprocessed(10)
    assert [r["message_id"] for r in claimed] == ["100", "101"]

    store.mark_processed("100")

    remaining = store.claim_unprocessed(10)
    assert [r["message_id"] for r in remaining] == ["101"]


def test_claim_respects_limit(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    for mid in ("100", "101", "102"):
        store.insert_message(_msg(mid))

    assert len(store.claim_unprocessed(2)) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_processed.py -v`
Expected: FAIL with `AttributeError: 'RawStore' object has no attribute 'claim_unprocessed'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/store.py`, at the END of the existing `init_db()` method's `with self._connect() as conn:` block (after the `messages` and `cursors` table creates), add the idempotent migration + index:
```python
            existing = [
                row["name"]
                for row in conn.execute("PRAGMA table_info(messages)").fetchall()
            ]
            if "processed_at" not in existing:
                conn.execute("ALTER TABLE messages ADD COLUMN processed_at TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_processed_at "
                "ON messages(processed_at)"
            )
```

Then add these two methods to the `RawStore` class:
```python
    def claim_unprocessed(self, limit: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE processed_at IS NULL "
                "ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_processed(self, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE messages SET processed_at = datetime('now') "
                "WHERE message_id = ?",
                (message_id,),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_processed.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the existing store tests (no regression)**

Run: `uv run pytest tests/test_store.py tests/test_cursor.py -v`
Expected: PASS (all green — the migration is additive).

- [ ] **Step 6: Commit**

```bash
git add backend/store.py tests/test_processed.py
git commit -m "feat: processed_at marker + claim_unprocessed/mark_processed on raw store"
```

---

### Task 2: Keyword pre-filter

**Files:**
- Create: `backend/filter.py`
- Test: `tests/test_filter.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `is_candidate(content: str) -> bool` — true when the message contains a URL **and** at least one opportunity keyword. Pure, free, tuned to over-include.

- [ ] **Step 1: Write the failing test**

Create `tests/test_filter.py`:
```python
from backend.filter import is_candidate


def test_url_plus_keyword_is_candidate():
    assert is_candidate("Apply now: https://org.org/jobs — deadline Friday") is True


def test_keyword_without_url_is_not_candidate():
    assert is_candidate("we are hiring, DM me") is False


def test_url_without_keyword_is_not_candidate():
    assert is_candidate("cool paper https://arxiv.org/abs/1234") is False


def test_plain_chatter_is_not_candidate():
    assert is_candidate("thanks, see you there!") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_filter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.filter'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/filter.py`:
```python
import re

_URL_RE = re.compile(r"https?://", re.IGNORECASE)

_KEYWORDS = (
    "apply",
    "deadline",
    "fellowship",
    "grant",
    "hiring",
    "internship",
    "intern",
    "cohort",
    "stipend",
    "scholarship",
    "position",
    "role",
    "rfp",
    "open call",
    "applications open",
    "now accepting",
    "residency",
    "bootcamp",
    "funding",
    "career",
    "program",
)


def is_candidate(content: str) -> bool:
    if not _URL_RE.search(content):
        return False
    text = content.lower()
    return any(keyword in text for keyword in _KEYWORDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_filter.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/filter.py tests/test_filter.py
git commit -m "feat: keyword pre-filter for opportunity candidates"
```

---

### Task 3: Opportunity model + LLM extractor

**Files:**
- Modify: `backend/models.py` (add `Opportunity`)
- Create: `backend/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (talks to an injected OpenAI-compatible client).
- Produces:
  - `Opportunity` pydantic model with fields `is_opportunity: bool`, `title: str | None`, `org: str | None`, `type: str | None`, `deadline: str | None`, `link: str | None`, `location: str | None`, `remote: bool` (default `False`).
  - `Extractor(client, model: str)` with `extract(content: str) -> Opportunity | None`. `client` is any object exposing `client.chat.completions.create(model=..., messages=..., response_format=..., temperature=...)` returning an object whose `.choices[0].message.content` is a JSON string. Returns `None` when `is_opportunity` is false; coerces an out-of-vocab `type` to `"other"`; retries once on invalid/short output; raises `ExtractionError` after the second failure.
  - `ExtractionError(Exception)`.
  - `VOCAB` (the fixed `type` set).

- [ ] **Step 1: Add the openai dependency**

Run:
```bash
cd /Users/kaustubhkislay/aisafety-opportunities
uv add openai
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_extract.py`:
```python
from types import SimpleNamespace

import pytest

from backend.extract import Extractor, ExtractionError


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        content = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


OPP_JSON = (
    '{"is_opportunity": true, "title": "ML Fellow", "org": "Redwood", '
    '"type": "fellowship", "deadline": "2026-08-01", '
    '"link": "https://redwood.org/apply", "location": "Remote", "remote": true}'
)


def test_extract_returns_opportunity():
    client = FakeClient([OPP_JSON])
    opp = Extractor(client, "qwen-test").extract("Apply: https://redwood.org/apply")
    assert opp is not None
    assert opp.title == "ML Fellow"
    assert opp.type == "fellowship"
    assert opp.remote is True


def test_out_of_vocab_type_coerced_to_other():
    client = FakeClient(['{"is_opportunity": true, "type": "workshop"}'])
    opp = Extractor(client, "qwen-test").extract("x")
    assert opp.type == "other"


def test_non_opportunity_returns_none():
    client = FakeClient(['{"is_opportunity": false}'])
    assert Extractor(client, "qwen-test").extract("thanks!") is None


def test_invalid_json_then_valid_retries():
    client = FakeClient(["not json at all", OPP_JSON])
    opp = Extractor(client, "qwen-test").extract("x")
    assert opp.title == "ML Fellow"
    assert client.chat.completions.calls == 2


def test_two_failures_raise():
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(ExtractionError):
        Extractor(client, "qwen-test").extract("x")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.extract'`.

- [ ] **Step 4: Write minimal implementation**

In `backend/models.py`, append the `Opportunity` model (keep the existing `IngestMessage`):
```python
class Opportunity(BaseModel):
    is_opportunity: bool
    title: str | None = None
    org: str | None = None
    type: str | None = None
    deadline: str | None = None
    link: str | None = None
    location: str | None = None
    remote: bool = False
```

Create `backend/extract.py`:
```python
import json

from pydantic import ValidationError

from backend.models import Opportunity

VOCAB = {
    "job",
    "internship",
    "fellowship",
    "grant",
    "event",
    "course",
    "reading-group",
    "other",
}

SYSTEM_PROMPT = (
    "You extract AI-safety opportunities from chat messages. "
    "Return ONLY a JSON object with these keys: "
    "is_opportunity (bool), title, org, type, deadline, link, location (strings or null), "
    "remote (bool). "
    "Set is_opportunity false for chatter, questions, reactions, or anything without a "
    "concrete opening, deadline, or application path. "
    f"type must be one of: {', '.join(sorted(VOCAB))}. "
    "deadline must be an ISO date (YYYY-MM-DD) or null. "
    "link must be the official application/info URL, or null. "
    "PRIVACY: never include an individual's personal contact details. Replace any personal "
    "email, phone number, or 'DM me'/handle with the official application link or email; if "
    "there is no official link, set link to null."
)


class ExtractionError(Exception):
    pass


class Extractor:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def _call(self, content: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return resp.choices[0].message.content

    def extract(self, content: str) -> Opportunity | None:
        last_err: Exception | None = None
        for _ in range(2):
            try:
                opp = Opportunity.model_validate_json(self._call(content))
                if not opp.is_opportunity:
                    return None
                if opp.type not in VOCAB:
                    opp.type = "other"
                return opp
            except (ValidationError, ValueError, json.JSONDecodeError) as err:
                last_err = err
        raise ExtractionError(f"extraction failed after retry: {last_err}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_extract.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock backend/models.py backend/extract.py tests/test_extract.py
git commit -m "feat: Opportunity model + open-model extractor with retry and vocab coercion"
```

---

### Task 4: Link-safety gate

**Files:**
- Create: `backend/linksafety.py`
- Test: `tests/test_linksafety.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `is_safe(url: str) -> tuple[bool, str]` returning `(ok, reason)`. Withholds shorteners, punycode/IDN hosts, and denylisted domains; unparseable hosts are unsafe; everything else passes. Pure function.

- [ ] **Step 1: Write the failing test**

Create `tests/test_linksafety.py`:
```python
from backend.linksafety import is_safe


def test_plain_domain_is_safe():
    ok, reason = is_safe("https://www.80000hours.org/jobs/abc")
    assert ok is True
    assert reason == "ok"


def test_shortener_is_withheld():
    ok, reason = is_safe("https://bit.ly/xyz")
    assert ok is False
    assert reason == "shortener"


def test_punycode_is_withheld():
    ok, reason = is_safe("https://xn--80ak6aa92e.com/apply")
    assert ok is False
    assert reason == "punycode"


def test_unparseable_is_withheld():
    ok, reason = is_safe("not a url")
    assert ok is False
    assert reason == "unparseable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_linksafety.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.linksafety'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/linksafety.py`:
```python
from urllib.parse import urlparse

_SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "buff.ly",
    "is.gd",
    "rebrand.ly",
}

_DENYLIST: set[str] = set()  # populated over time as bad actors are found


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_safe(url: str) -> tuple[bool, str]:
    host = _host(url)
    if not host:
        return (False, "unparseable")
    if host in _DENYLIST:
        return (False, "denylisted")
    if host in _SHORTENERS:
        return (False, "shortener")
    if host.startswith("xn--") or ".xn--" in host:
        return (False, "punycode")
    return (True, "ok")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_linksafety.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/linksafety.py tests/test_linksafety.py
git commit -m "feat: rule-based link-safety gate"
```

---

### Task 5: Dedup key

**Files:**
- Create: `backend/dedup.py`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Consumes: the `Opportunity` model (Task 3) — reads `.link`, `.org`, `.title`, `.deadline`.
- Produces: `normalize_url(url: str) -> str` and `stable_key(opp) -> str`. Key is `"url:" + normalize_url(link)` when a link exists, else `"meta:" + sha256(org|title|deadline)[:16]`. URL normalization lowercases the host, drops `www.`, strips a trailing slash, removes tracking query params (utm_*, fbclid, gclid, ref), and sorts the remaining query.

- [ ] **Step 1: Write the failing test**

Create `tests/test_dedup.py`:
```python
from backend.models import Opportunity
from backend.dedup import stable_key


def _opp(**kw):
    base = {"is_opportunity": True}
    base.update(kw)
    return Opportunity(**base)


def test_same_url_different_case_and_tracking_dedupes():
    a = _opp(link="https://WWW.Org.org/Apply/?utm_source=x")
    b = _opp(link="https://org.org/Apply")
    assert stable_key(a) == stable_key(b)
    assert stable_key(a).startswith("url:")


def test_no_link_uses_meta_hash():
    a = _opp(org="Redwood", title="ML Fellow", deadline="2026-08-01")
    key = stable_key(a)
    assert key.startswith("meta:")
    # deterministic
    assert key == stable_key(_opp(org="Redwood", title="ML Fellow", deadline="2026-08-01"))


def test_different_title_different_meta_key():
    a = _opp(org="Redwood", title="ML Fellow")
    b = _opp(org="Redwood", title="SWE Intern")
    assert stable_key(a) != stable_key(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.dedup'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/dedup.py`:
```python
import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse

_TRACKING = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    query_items = sorted(
        (k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKING
    )
    base = host + path
    if query_items:
        base += "?" + urlencode(query_items)
    return base


def stable_key(opp) -> str:
    if opp.link:
        return "url:" + normalize_url(opp.link)
    basis = f"{(opp.org or '').lower()}|{(opp.title or '').lower()}|{opp.deadline or ''}"
    return "meta:" + hashlib.sha256(basis.encode()).hexdigest()[:16]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dedup.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/dedup.py tests/test_dedup.py
git commit -m "feat: stable dedup key with URL normalization"
```

---

### Task 6: Airtable upsert client

**Files:**
- Create: `backend/airtable.py`
- Test: `tests/test_airtable.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `AirtableStore(backend)` with `upsert(fields: dict, dedup_key: str) -> tuple[str, str]` returning `(record_id, "created" | "updated")`. `backend` exposes `find_by_dedup_key(key) -> dict | None` (a record with an `"id"` key), `create(fields) -> str` (returns the new record id), and `update(record_id, fields) -> None`.
  - `PyairtableBackend(table)` implementing that interface over a `pyairtable` table.
  - `backend_from_env() -> PyairtableBackend` building the table from `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID`/`AIRTABLE_TABLE_NAME`.

- [ ] **Step 1: Add the pyairtable dependency**

Run:
```bash
cd /Users/kaustubhkislay/aisafety-opportunities
uv add pyairtable
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_airtable.py`:
```python
from backend.airtable import AirtableStore


class FakeBackend:
    def __init__(self):
        self.records: dict[str, dict] = {}
        self._counter = 0

    def find_by_dedup_key(self, key):
        for rid, fields in self.records.items():
            if fields.get("dedup_key") == key:
                return {"id": rid, "fields": fields}
        return None

    def create(self, fields) -> str:
        self._counter += 1
        rid = f"rec{self._counter}"
        self.records[rid] = dict(fields)
        return rid

    def update(self, record_id, fields) -> None:
        self.records[record_id].update(fields)


def test_upsert_creates_then_updates():
    backend = FakeBackend()
    store = AirtableStore(backend)

    rid, action = store.upsert({"title": "ML Fellow", "dedup_key": "url:org.org/apply"}, "url:org.org/apply")
    assert action == "created"
    assert backend.records[rid]["title"] == "ML Fellow"

    rid2, action2 = store.upsert(
        {"title": "ML Fellow (updated deadline)", "dedup_key": "url:org.org/apply"},
        "url:org.org/apply",
    )
    assert action2 == "updated"
    assert rid2 == rid  # same record, not a duplicate
    assert backend.records[rid]["title"] == "ML Fellow (updated deadline)"
    assert len(backend.records) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_airtable.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.airtable'`.

- [ ] **Step 4: Write minimal implementation**

Create `backend/airtable.py`:
```python
import os


class AirtableStore:
    def __init__(self, backend):
        self.backend = backend

    def upsert(self, fields: dict, dedup_key: str) -> tuple[str, str]:
        existing = self.backend.find_by_dedup_key(dedup_key)
        if existing is not None:
            self.backend.update(existing["id"], fields)
            return existing["id"], "updated"
        record_id = self.backend.create(fields)
        return record_id, "created"


class PyairtableBackend:
    def __init__(self, table):
        self.table = table

    def find_by_dedup_key(self, key):
        from pyairtable.formulas import match

        return self.table.first(formula=match({"dedup_key": key}))

    def create(self, fields) -> str:
        return self.table.create(fields)["id"]

    def update(self, record_id, fields) -> None:
        self.table.update(record_id, fields)


def backend_from_env() -> PyairtableBackend:
    from pyairtable import Api

    api = Api(os.environ["AIRTABLE_API_KEY"])
    table = api.table(os.environ["AIRTABLE_BASE_ID"], os.environ["AIRTABLE_TABLE_NAME"])
    return PyairtableBackend(table)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_airtable.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock backend/airtable.py tests/test_airtable.py
git commit -m "feat: Airtable upsert client keyed on dedup_key"
```

---

### Task 7: Worker — pipeline + poll loop

**Files:**
- Create: `backend/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `is_candidate` (Task 2), `Extractor`/`ExtractionError` (Task 3), `is_safe` (Task 4), `stable_key` (Task 5), `AirtableStore`/`backend_from_env` (Task 6), `RawStore` (Task 1), `Opportunity` (Task 3).
- Produces:
  - `build_fields(opp, row, dedup_key, model_name) -> dict` — maps an `Opportunity` + a raw `messages` row to the 14 Airtable field names.
  - `process_message(row, *, extractor, store, model_name, filter_fn=is_candidate, link_check=is_safe, key_fn=stable_key) -> str` — runs one row through the pipeline; returns one of `"skipped_filter" | "not_opportunity" | "withheld" | "created" | "updated"`; propagates `ExtractionError`/Airtable errors (caller leaves the row unprocessed).
  - `run_worker(raw_store, process_fn, *, batch_size, poll_interval, sleep=time.sleep, max_loops=None)` — claims batches and calls `process_fn(row)`; on success marks processed; on any exception logs and leaves the row unprocessed; sleeps when a batch is empty.
  - `main()` — wires everything from env and runs forever.

- [ ] **Step 1: Write the failing test**

Create `tests/test_worker.py`:
```python
from backend.models import Opportunity
from backend.worker import build_fields, process_message, run_worker


ROW = {
    "message_id": "100",
    "server_id": "srv1",
    "channel_id": "chan1",
    "content": "Apply: https://redwood.org/apply — fellowship, deadline 2026-08-01",
    "created_at": "2026-06-25T12:00:00+00:00",
    "ingested_at": "2026-06-25 12:00:05",
}


class StubExtractor:
    def __init__(self, result):
        self._result = result

    def extract(self, content):
        return self._result


class RecordingStore:
    def __init__(self):
        self.upserts = []

    def upsert(self, fields, dedup_key):
        self.upserts.append((fields, dedup_key))
        return "rec1", "created"


def _opp(**kw):
    base = {"is_opportunity": True}
    base.update(kw)
    return Opportunity(**base)


def test_build_fields_maps_row_and_opportunity():
    opp = _opp(title="ML Fellow", org="Redwood", type="fellowship",
               deadline="2026-08-01", link="https://redwood.org/apply",
               location="Remote", remote=True)
    fields = build_fields(opp, ROW, "url:redwood.org/apply", "qwen-test")
    assert fields["title"] == "ML Fellow"
    assert fields["type"] == "fellowship"
    assert fields["remote"] is True
    assert fields["source_server"] == "srv1"
    assert fields["source_channel"] == "chan1"
    assert fields["raw_text"] == ROW["content"]
    assert fields["date_seen"] == "2026-06-25"
    assert fields["dedup_key"] == "url:redwood.org/apply"
    assert fields["llm_model"] == "qwen-test"


def test_process_filtered_out():
    status = process_message(
        {"message_id": "1", "content": "thanks!"},
        extractor=StubExtractor(None), store=RecordingStore(), model_name="m",
    )
    assert status == "skipped_filter"


def test_process_not_opportunity():
    status = process_message(
        ROW, extractor=StubExtractor(None), store=RecordingStore(), model_name="m",
    )
    assert status == "not_opportunity"


def test_process_withheld_on_unsafe_link():
    opp = _opp(title="x", link="https://bit.ly/abc")
    store = RecordingStore()
    status = process_message(ROW, extractor=StubExtractor(opp), store=store, model_name="m")
    assert status == "withheld"
    assert store.upserts == []  # nothing published


def test_process_creates_record():
    opp = _opp(title="ML Fellow", org="Redwood", link="https://redwood.org/apply")
    store = RecordingStore()
    status = process_message(ROW, extractor=StubExtractor(opp), store=store, model_name="m")
    assert status == "created"
    assert len(store.upserts) == 1


class FakeRawStore:
    def __init__(self, batches):
        self._batches = list(batches)
        self.marked = []

    def claim_unprocessed(self, limit):
        return self._batches.pop(0) if self._batches else []

    def mark_processed(self, message_id):
        self.marked.append(message_id)


def test_run_worker_marks_success_and_leaves_failures():
    rows = [{"message_id": "ok"}, {"message_id": "boom"}]
    raw = FakeRawStore([rows])

    def process_fn(row):
        if row["message_id"] == "boom":
            raise RuntimeError("LLM down")
        return "created"

    run_worker(raw, process_fn, batch_size=10, poll_interval=0,
               sleep=lambda _s: None, max_loops=1)

    assert raw.marked == ["ok"]  # "boom" left unprocessed for retry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.worker'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/worker.py`:
```python
import logging
import os
import time

from backend.airtable import AirtableStore, backend_from_env
from backend.dedup import stable_key
from backend.extract import Extractor
from backend.filter import is_candidate
from backend.linksafety import is_safe
from backend.store import RawStore

log = logging.getLogger("worker")


def build_fields(opp, row, dedup_key: str, model_name: str) -> dict:
    seen = row.get("ingested_at") or row["created_at"]
    return {
        "title": opp.title or "",
        "org": opp.org or "",
        "type": opp.type or "other",
        "deadline": opp.deadline,
        "link": opp.link or "",
        "location": opp.location or "",
        "remote": bool(opp.remote),
        "source_server": row["server_id"],
        "source_channel": row["channel_id"],
        "raw_text": row["content"],
        "date_seen": seen[:10],
        "dedup_key": dedup_key,
        "llm_model": model_name,
    }


def process_message(
    row,
    *,
    extractor,
    store,
    model_name: str,
    filter_fn=is_candidate,
    link_check=is_safe,
    key_fn=stable_key,
) -> str:
    content = row["content"]
    if not filter_fn(content):
        return "skipped_filter"
    opp = extractor.extract(content)  # raises on hard failure -> caller leaves unprocessed
    if opp is None:
        return "not_opportunity"
    if opp.link:
        safe, reason = link_check(opp.link)
        if not safe:
            log.warning("withheld %s (%s): %s", row.get("message_id"), reason, opp.link)
            return "withheld"
    key = key_fn(opp)
    _record_id, action = store.upsert(build_fields(opp, row, key, model_name), key)
    return action


def run_worker(
    raw_store,
    process_fn,
    *,
    batch_size: int,
    poll_interval: float,
    sleep=time.sleep,
    max_loops=None,
) -> None:
    loops = 0
    while max_loops is None or loops < max_loops:
        rows = raw_store.claim_unprocessed(batch_size)
        for row in rows:
            try:
                process_fn(row)
            except Exception:  # noqa: BLE001 - leave unprocessed, retry next loop
                log.exception(
                    "processing failed for %s; leaving unprocessed",
                    row.get("message_id"),
                )
                continue
            raw_store.mark_processed(row["message_id"])
        if not rows:
            sleep(poll_interval)
        loops += 1


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    raw_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
    raw_store.init_db()

    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    model = os.environ["OPENAI_MODEL"]
    extractor = Extractor(client, model)
    store = AirtableStore(backend_from_env())

    def process_fn(row):
        return process_message(row, extractor=extractor, store=store, model_name=model)

    run_worker(
        raw_store,
        process_fn,
        batch_size=int(os.environ.get("WORKER_BATCH_SIZE", "20")),
        poll_interval=float(os.environ.get("WORKER_POLL_INTERVAL", "10")),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_worker.py -v`
Expected: PASS (6 passed). (`test_process_creates_record` passes because `RecordingStore.upsert` returns `("rec1", "created")`.)

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS — all Slice 1 + Slice 2 tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/worker.py tests/test_worker.py
git commit -m "feat: extraction worker — pipeline and poll loop"
```

---

## Manual verification (after all tasks)

End-to-end against the real Airtable base and a real open-weights endpoint:

1. Fill `.env`: `OPENAI_BASE_URL` (e.g. `https://openrouter.ai/api/v1`), `OPENAI_API_KEY`, `OPENAI_MODEL` (a Qwen instruct model id); `AIRTABLE_*` are already set.
2. Seed the raw store with a real opportunity message (run the Slice 1 bot on a test server and post one, or insert one: `uv run python -c "from backend.store import RawStore; s=RawStore('raw.db'); s.init_db(); s.insert_message({'server_id':'demo','channel_id':'jobs','message_id':'t1','author_id':'u','content':'Fellowship open! Apply at https://example.org/apply by 2026-09-01','created_at':'2026-06-25T12:00:00+00:00'})"`).
3. Run the worker once: `uv run python -m backend.worker` (Ctrl-C after it processes the batch), or temporarily call `run_worker(..., max_loops=1)`.
4. Confirm a record appeared in the Airtable "Opportunities" table with the extracted fields and a `dedup_key`.
5. Re-run — confirm no duplicate (the same `dedup_key` updates the existing record).

## Out of scope for this plan (later slices)

Semantic/embedding dedup; external link-reputation APIs; the public website + RSS + search (Slice 3); the email digest; the daily deadline-status job; multi-language handling; surfacing withheld items in a review UI; backoff/queue infrastructure beyond "leave unprocessed and retry".
