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
        self.purged_servers: list[str] = []

    def delete_by_message(self, message_id: str) -> bool:
        self.deleted.append(message_id)
        return True

    def delete_by_server(self, server_id: str) -> int:
        self.purged_servers.append(server_id)
        return 1


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
