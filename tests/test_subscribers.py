import importlib

from fastapi.testclient import TestClient

from backend.subscribers import SubscriberStore


def _store(tmp_path):
    s = SubscriberStore(str(tmp_path / "subs.db"))
    s.init_db()
    return s


def test_add_is_idempotent(tmp_path):
    s = _store(tmp_path)
    assert s.add("a@x.com") is True
    assert s.add("a@x.com") is False  # already subscribed
    assert s.active_emails() == ["a@x.com"]


def test_remove(tmp_path):
    s = _store(tmp_path)
    s.add("a@x.com")
    assert s.remove("a@x.com") is True
    assert s.active_emails() == []
    assert s.remove("a@x.com") is False  # already inactive


def test_resubscribe_reactivates(tmp_path):
    s = _store(tmp_path)
    s.add("a@x.com")
    s.remove("a@x.com")
    assert s.add("a@x.com") is True  # reactivated, counts as a change
    assert s.active_emails() == ["a@x.com"]


def test_email_is_normalized(tmp_path):
    s = _store(tmp_path)
    assert s.add("  A@X.com ") is True
    assert s.active_emails() == ["a@x.com"]
    assert s.add("a@x.com") is False  # same address after normalization


# --- /subscribe and /unsubscribe endpoints --------------------------------

def _api(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("SUBSCRIBER_DB_PATH", str(tmp_path / "subs.db"))
    monkeypatch.setenv("INGEST_SHARED_SECRET", "s3cret")
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "unsub-secret")
    import backend.app as app_module
    importlib.reload(app_module)
    return app_module, TestClient(app_module.app)


def test_subscribe_endpoint_stores_valid_email(tmp_path, monkeypatch):
    # Double-opt-in: without a configured sender (dev), the address activates
    # directly; with one, it stays pending until the confirm link is clicked.
    mod, client = _api(tmp_path, monkeypatch)
    resp = client.post("/subscribe", json={"email": "A@x.com"})
    assert resp.status_code == 200
    assert resp.json() == {"pending": True, "email": "a@x.com"}
    assert mod._subscribers.active_emails() == ["a@x.com"]  # dev fallback activates


def test_subscribe_endpoint_rejects_invalid_email(tmp_path, monkeypatch):
    _mod, client = _api(tmp_path, monkeypatch)
    assert client.post("/subscribe", json={"email": "nope"}).status_code == 400


def test_unsubscribe_endpoint_removes_subscriber(tmp_path, monkeypatch):
    from backend.digest import make_token
    mod, client = _api(tmp_path, monkeypatch)
    mod._subscribers.add("a@x.com")
    token = make_token("a@x.com", "unsub-secret")
    resp = client.get(f"/unsubscribe?token={token}")
    assert resp.status_code == 200
    assert "unsubscribed" in resp.text
    assert mod._subscribers.active_emails() == []


def test_unsubscribe_endpoint_rejects_bad_token(tmp_path, monkeypatch):
    _mod, client = _api(tmp_path, monkeypatch)
    assert client.get("/unsubscribe?token=garbage").status_code == 400


def test_add_pending_then_activate(tmp_path):
    store = _store(tmp_path)
    assert store.add_pending("new@x.com") is True
    assert store.active_emails() == []  # pending, not active
    assert store.activate("new@x.com") is True
    assert store.active_emails() == ["new@x.com"]
    assert store.activate("new@x.com") is False  # idempotent


def test_add_pending_does_not_deactivate_existing(tmp_path):
    store = _store(tmp_path)
    store.add("old@x.com")
    assert store.add_pending("old@x.com") is False
    assert store.active_emails() == ["old@x.com"]
