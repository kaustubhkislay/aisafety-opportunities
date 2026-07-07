import importlib
import json

import httpx
from fastapi.testclient import TestClient

from backend.airtable import AirtableStore
from backend.purge import purge_server
from backend.store import RawStore
from bot.forwarder import Forwarder


def _raw(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    return store


def _insert(store, message_id, server_id):
    store.insert_message({
        "server_id": server_id, "channel_id": "c", "message_id": message_id,
        "author_id": "u", "content": "x", "created_at": "2026-06-25T12:00:00+00:00",
    })


# --- RawStore: list + delete by server ------------------------------------

def test_rawstore_list_and_delete_by_server(tmp_path):
    store = _raw(tmp_path)
    _insert(store, "1", "A")
    _insert(store, "2", "A")
    _insert(store, "3", "B")

    assert {m["message_id"] for m in store.get_messages_by_server("A")} == {"1", "2"}

    deleted = store.delete_server("A")
    assert deleted == 2
    assert store.get_messages_by_server("A") == []
    assert {m["message_id"] for m in store.get_messages_by_server("B")} == {"3"}


# --- AirtableStore: delete by server --------------------------------------

class FakeBackend:
    def __init__(self, records):
        self.records = records  # list of {"id", "fields"}
        self.deleted = []

    def find_by_server(self, server_id):
        return [r for r in self.records if r["fields"].get("source_server") == server_id]

    def delete(self, record_id):
        self.deleted.append(record_id)

    def all(self):
        return [r for r in self.records if r["id"] not in self.deleted]

    def update(self, record_id, fields):
        for r in self.records:
            if r["id"] == record_id:
                r["fields"].update(fields)


def test_delete_by_server_deletes_all_matching():
    records = [
        {"id": "r1", "fields": {"source_server": "A"}},
        {"id": "r2", "fields": {"source_server": "A"}},
        {"id": "r3", "fields": {"source_server": "B"}},
    ]
    store = AirtableStore(FakeBackend(records))
    assert store.delete_by_server("A") == 2
    assert store.backend.deleted == ["r1", "r2"]


# --- purge_server orchestration -------------------------------------------

def test_purge_server_clears_both_stores(tmp_path):
    raw = _raw(tmp_path)
    _insert(raw, "1", "A")
    _insert(raw, "2", "A")
    _insert(raw, "3", "B")
    airtable = AirtableStore(FakeBackend([
        {"id": "r1", "fields": {"source_server": "A"}},
        {"id": "r2", "fields": {"source_server": "A"}},
        {"id": "r3", "fields": {"source_server": "B"}},
    ]))

    result = purge_server(airtable, raw, "A")

    assert result == {"airtable": 2, "scrubbed": 0, "raw": 2}
    assert raw.get_messages_by_server("A") == []
    assert {m["message_id"] for m in raw.get_messages_by_server("B")} == {"3"}


# --- bot: Forwarder.purge -------------------------------------------------

async def test_forwarder_purge_posts_server_id_with_secret():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["secret"] = request.headers.get("x-ingest-secret")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"airtable": 0, "raw": 0})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    forwarder = Forwarder("http://api.local", "s3cret", client=client)

    status = await forwarder.purge("A")

    assert status == 200
    assert seen["url"] == "http://api.local/purge"
    assert seen["secret"] == "s3cret"
    assert seen["body"] == {"server_id": "A"}
    await client.aclose()


# --- backend endpoints: /purge and /ingested ------------------------------

def _api(tmp_path, monkeypatch, fake_airtable):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("INGEST_SHARED_SECRET", "s3cret")
    import backend.app as app_module
    importlib.reload(app_module)
    app_module.app.dependency_overrides[app_module.get_airtable_store] = lambda: fake_airtable
    return app_module, TestClient(app_module.app)


def test_purge_endpoint_rejects_bad_secret(tmp_path, monkeypatch):
    airtable = AirtableStore(FakeBackend([]))
    _mod, client = _api(tmp_path, monkeypatch, airtable)
    resp = client.post("/purge", json={"server_id": "A"}, headers={"X-Ingest-Secret": "wrong"})
    assert resp.status_code == 401


def test_purge_endpoint_clears_server(tmp_path, monkeypatch):
    airtable = AirtableStore(FakeBackend([
        {"id": "r1", "fields": {"source_server": "A"}},
    ]))
    mod, client = _api(tmp_path, monkeypatch, airtable)
    _insert(mod._store, "1", "A")
    _insert(mod._store, "2", "B")

    resp = client.post("/purge", json={"server_id": "A"}, headers={"X-Ingest-Secret": "s3cret"})

    assert resp.status_code == 200
    assert resp.json() == {"server_id": "A", "airtable": 1, "scrubbed": 0, "raw": 1}
    assert mod._store.get_messages_by_server("A") == []
    assert len(mod._store.get_messages_by_server("B")) == 1


def test_ingested_endpoint_returns_server_messages(tmp_path, monkeypatch):
    airtable = AirtableStore(FakeBackend([]))
    mod, client = _api(tmp_path, monkeypatch, airtable)
    _insert(mod._store, "1", "A")
    _insert(mod._store, "2", "A")
    _insert(mod._store, "3", "B")

    resp = client.get("/ingested/A", headers={"X-Ingest-Secret": "s3cret"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["server_id"] == "A"
    assert body["count"] == 2
    assert {m["message_id"] for m in body["messages"]} == {"1", "2"}


def test_ingested_endpoint_rejects_bad_secret(tmp_path, monkeypatch):
    airtable = AirtableStore(FakeBackend([]))
    _mod, client = _api(tmp_path, monkeypatch, airtable)
    resp = client.get("/ingested/A", headers={"X-Ingest-Secret": "wrong"})
    assert resp.status_code == 401


# --- Purge scrubs attribution from surviving merged records ----------------

class RichFakeBackend:
    """Fake with the full surface purge needs: find/delete/all/update."""

    def __init__(self, records):
        self.records = {r["id"]: dict(r["fields"]) for r in records}
        self.updates: list[tuple[str, dict]] = []

    def find_by_server(self, server_id):
        return [{"id": rid, "fields": f} for rid, f in self.records.items()
                if f.get("source_server") == server_id]

    def delete(self, record_id):
        self.records.pop(record_id, None)

    def all(self):
        return [{"id": rid, "fields": dict(f)} for rid, f in self.records.items()]

    def update(self, record_id, fields):
        self.records[record_id].update(fields)
        self.updates.append((record_id, fields))


def test_purge_scrubs_name_from_surviving_merged_records(tmp_path):
    raw = _raw(tmp_path)
    raw.insert_message({
        "server_id": "slack:T1", "server_name": "Uni Slack", "channel_id": "c",
        "message_id": "m1", "author_id": "u", "content": "x",
        "created_at": "2026-07-07T12:00:00+00:00",
    })
    backend = RichFakeBackend([
        # r1's latest source is the purged workspace -> deleted outright
        {"id": "r1", "fields": {"source_server": "slack:T1",
                                "source_servers": "Uni Slack"}},
        # r2 is a merged record whose latest source is another community ->
        # survives, but the purged community's attribution must be scrubbed
        {"id": "r2", "fields": {"source_server": "999",
                                "source_servers": "Other Discord, Uni Slack"}},
        # r3 untouched
        {"id": "r3", "fields": {"source_server": "888",
                                "source_servers": "Third"}},
    ])
    store = AirtableStore(backend)

    counts = purge_server(store, raw, "slack:T1")

    assert counts == {"airtable": 1, "scrubbed": 1, "raw": 1}
    assert "r1" not in backend.records
    assert backend.records["r2"]["source_servers"] == "Other Discord"
    assert backend.records["r3"]["source_servers"] == "Third"


def test_purge_scrubs_server_id_when_name_unknown(tmp_path):
    # Records whose source_servers fell back to the raw server_id (no name)
    raw = _raw(tmp_path)
    backend = RichFakeBackend([
        {"id": "r1", "fields": {"source_server": "999",
                                "source_servers": "Other, slack:T1"}},
    ])
    counts = purge_server(AirtableStore(backend), raw, "slack:T1")
    assert counts["scrubbed"] == 1
    assert backend.records["r1"]["source_servers"] == "Other"
