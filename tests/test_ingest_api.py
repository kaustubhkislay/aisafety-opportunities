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


def test_retract_pings_revalidate(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    import backend.app as app_module

    pings = []
    monkeypatch.setattr(app_module, "_revalidator", lambda: pings.append(1) or True)

    class FakeStore:
        def delete_by_message(self, message_id):
            return 1

    app_module.app.dependency_overrides[app_module.get_airtable_store] = FakeStore
    try:
        resp = client.post(
            "/retract", json={"message_id": "m1"},
            headers={"X-Ingest-Secret": "s3cret"},
        )
    finally:
        app_module.app.dependency_overrides.pop(app_module.get_airtable_store, None)
    assert resp.status_code == 200
    assert pings == [1]  # site refreshed so the retraction is visible immediately
