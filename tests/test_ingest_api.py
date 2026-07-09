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



def test_subscribe_is_double_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBSCRIBER_DB_PATH", str(tmp_path / "subs.db"))
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "sek")
    client = _client(tmp_path, monkeypatch)
    import backend.app as app_module

    sent = []
    monkeypatch.setattr(app_module, "_confirm_sender", lambda: (lambda e, s, h, t: sent.append((e, h))))
    resp = client.post("/subscribe", json={"email": "new@x.com"})
    assert resp.status_code == 200
    assert resp.json()["pending"] is True
    assert app_module._subscribers.active_emails() == []  # not active yet
    assert len(sent) == 1 and "confirm" in sent[0][1].lower()

    # follow the confirm link
    from backend.digest import make_token

    token = make_token("new@x.com", "sek", purpose="confirm")
    resp = client.get(f"/subscribe/confirm?token={token}")
    assert resp.status_code == 200
    assert app_module._subscribers.active_emails() == ["new@x.com"]


def test_subscribe_rate_limited_per_ip(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBSCRIBER_DB_PATH", str(tmp_path / "subs.db"))
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "sek")
    client = _client(tmp_path, monkeypatch)
    import backend.app as app_module

    monkeypatch.setattr(app_module, "_confirm_sender", lambda: (lambda *a: None))
    for i in range(5):
        assert client.post("/subscribe", json={"email": f"u{i}@x.com"}).status_code == 200
    assert client.post("/subscribe", json={"email": "u6@x.com"}).status_code == 429


def test_subscribe_rate_limit_uses_fly_client_ip(tmp_path, monkeypatch):
    # Behind Fly's proxy every request shares request.client.host; the real
    # client address arrives in Fly-Client-IP. Distinct header values must get
    # distinct buckets, and the same value must share one.
    monkeypatch.setenv("SUBSCRIBER_DB_PATH", str(tmp_path / "subs.db"))
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "sek")
    client = _client(tmp_path, monkeypatch)
    import backend.app as app_module

    monkeypatch.setattr(app_module, "_confirm_sender", lambda: (lambda *a: None))
    attacker = {"Fly-Client-IP": "203.0.113.9"}
    for i in range(5):
        resp = client.post("/subscribe", json={"email": f"a{i}@x.com"}, headers=attacker)
        assert resp.status_code == 200
    assert client.post("/subscribe", json={"email": "a6@x.com"}, headers=attacker).status_code == 429

    # A different real client is unaffected even though the proxy IP is identical.
    other = {"Fly-Client-IP": "198.51.100.7"}
    assert client.post("/subscribe", json={"email": "b1@x.com"}, headers=other).status_code == 200


def test_subscribe_confirm_emails_capped_per_address(tmp_path, monkeypatch):
    # Email-bombing guard: repeated signups for the same address may not keep
    # sending confirmation emails, but must not leak that via the response.
    monkeypatch.setenv("SUBSCRIBER_DB_PATH", str(tmp_path / "subs.db"))
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "sek")
    client = _client(tmp_path, monkeypatch)
    import backend.app as app_module

    sent = []
    monkeypatch.setattr(app_module, "_confirm_sender", lambda: (lambda e, *a: sent.append(e)))
    ips = [{"Fly-Client-IP": f"203.0.113.{i}"} for i in range(6)]  # dodge the IP limit
    for headers in ips:
        resp = client.post("/subscribe", json={"email": "victim@x.com"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["pending"] is True  # response identical whether or not we sent
    assert sent.count("victim@x.com") == 3  # capped, not one-per-request
