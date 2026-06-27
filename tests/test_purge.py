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

    assert result == {"airtable": 2, "raw": 2}
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
    assert resp.json() == {"server_id": "A", "airtable": 1, "raw": 1}
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
