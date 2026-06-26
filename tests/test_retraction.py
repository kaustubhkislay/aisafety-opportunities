import importlib
import json

import httpx
from fastapi.testclient import TestClient

from backend.airtable import AirtableStore
from backend.models import Opportunity
from backend.worker import build_fields
from bot.forwarder import Forwarder
from bot.retraction import LOCK_EMOJI, is_retraction_edit, is_retraction_reaction


# --- bot: signal detection -------------------------------------------------

def test_lock_emoji_is_a_retraction():
    assert is_retraction_reaction(LOCK_EMOJI) is True


def test_other_emoji_is_not_a_retraction():
    assert is_retraction_reaction("\U0001F44D") is False  # 👍


def test_edit_adding_private_tag_is_a_retraction():
    assert is_retraction_edit("oops, marking this [private] now") is True


def test_edit_without_tag_is_not_a_retraction():
    assert is_retraction_edit("just fixing a typo") is False


def test_edit_none_content_is_not_a_retraction():
    assert is_retraction_edit(None) is False


# --- bot: retraction call reuses the Forwarder/backend contract ------------

async def test_forwarder_retract_posts_message_id_with_secret():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["secret"] = request.headers.get("x-ingest-secret")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"deleted": True, "message_id": "100"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    forwarder = Forwarder("http://api.local", "s3cret", client=client)

    status = await forwarder.retract("100")

    assert status == 200
    assert seen["url"] == "http://api.local/retract"
    assert seen["secret"] == "s3cret"
    assert seen["body"] == {"message_id": "100"}
    await client.aclose()


# --- backend: delete-by-source-message ------------------------------------

class FakeBackend:
    def __init__(self, record):
        self.record = record  # {"id": ...} or None
        self.deleted = []
        self.looked_up = None

    def find_by_message_id(self, message_id):
        self.looked_up = message_id
        return self.record

    def delete(self, record_id):
        self.deleted.append(record_id)


def test_delete_by_message_deletes_when_found():
    backend = FakeBackend(record={"id": "recX"})
    store = AirtableStore(backend)
    assert store.delete_by_message("100") is True
    assert backend.looked_up == "100"
    assert backend.deleted == ["recX"]


def test_delete_by_message_returns_false_when_absent():
    backend = FakeBackend(record=None)
    store = AirtableStore(backend)
    assert store.delete_by_message("100") is False
    assert backend.deleted == []


# --- worker stamps source_message_id so records are retractable -----------

def test_build_fields_includes_source_message_id():
    opp = Opportunity(is_opportunity=True, title="t", org="o", type="job")
    row = {
        "server_id": "1", "channel_id": "10", "message_id": "100",
        "content": "c", "created_at": "2026-06-25T12:00:00",
        "ingested_at": "2026-06-25T12:00:00",
    }
    fields = build_fields(opp, row, "url:x", "model-x")
    assert fields["source_message_id"] == "100"


# --- backend: /retract endpoint -------------------------------------------

def _api(tmp_path, monkeypatch, fake_store):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("INGEST_SHARED_SECRET", "s3cret")
    import backend.app as app_module
    importlib.reload(app_module)
    app_module.app.dependency_overrides[app_module.get_airtable_store] = lambda: fake_store
    return app_module, TestClient(app_module.app)


def test_retract_rejects_bad_secret(tmp_path, monkeypatch):
    store = AirtableStore(FakeBackend(record={"id": "recX"}))
    _mod, client = _api(tmp_path, monkeypatch, store)
    resp = client.post("/retract", json={"message_id": "100"}, headers={"X-Ingest-Secret": "wrong"})
    assert resp.status_code == 401


def test_retract_deletes_record_and_tombstones_raw_message(tmp_path, monkeypatch):
    store = AirtableStore(FakeBackend(record={"id": "recX"}))
    mod, client = _api(tmp_path, monkeypatch, store)
    mod._store.insert_message({
        "server_id": "1", "channel_id": "10", "message_id": "100",
        "author_id": "5", "content": "Grant: https://x.org", "created_at": "2026-06-25T12:00:00+00:00",
    })

    resp = client.post("/retract", json={"message_id": "100"}, headers={"X-Ingest-Secret": "s3cret"})

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "message_id": "100"}
    # tombstoned: the worker will never (re)extract it
    assert mod._store.claim_unprocessed(10) == []
