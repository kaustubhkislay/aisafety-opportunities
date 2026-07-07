import importlib
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_DB_PATH", str(tmp_path / "raw.db"))
    monkeypatch.setenv("SLACK_TOKEN_DB_PATH", str(tmp_path / "slack_tokens.db"))
    monkeypatch.setenv("SLACK_CLIENT_ID", "cid.123")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
    monkeypatch.setenv("SLACK_REDIRECT_URL", "https://api.example.org/slack/oauth/callback")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "sgn")
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


def _state():
    import time

    from slackbot.verify import make_state

    return make_state("sgn", now=time.time())


def test_callback_exchanges_code_and_saves_install(tmp_path, monkeypatch):
    client, slack_module = _setup(tmp_path, monkeypatch)
    seen = {}

    async def fake_oauth_access(client_id, client_secret, code, redirect_uri):
        seen.update(code=code, client_id=client_id)
        return {"ok": True, "access_token": "xoxb-new",
                "team": {"id": "T9", "name": "New Workspace"},
                "bot_user_id": "U77"}

    monkeypatch.setattr(slack_module._web, "oauth_access", fake_oauth_access)
    resp = client.get(f"/slack/oauth/callback?code=thecode&state={_state()}")
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
    resp = client.get(f"/slack/oauth/callback?code=bad&state={_state()}")
    assert resp.status_code == 502


def test_callback_malformed_response_is_502_and_not_saved(tmp_path, monkeypatch):
    client, slack_module = _setup(tmp_path, monkeypatch)

    async def missing_team_oauth_access(client_id, client_secret, code, redirect_uri):
        return {"ok": True, "access_token": "xoxb-new", "bot_user_id": "U77"}

    monkeypatch.setattr(slack_module._web, "oauth_access", missing_team_oauth_access)
    resp = client.get(f"/slack/oauth/callback?code=thecode&state={_state()}")
    assert resp.status_code == 502
    assert slack_module._tokens.get("") is None


def test_install_carries_signed_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "sgn")
    client, slack_module = _setup(tmp_path, monkeypatch)
    resp = client.get("/slack/install")
    q = parse_qs(urlparse(resp.headers["location"]).query)
    from slackbot.verify import verify_state

    assert verify_state("sgn", q["state"][0], now=__import__("time").time()) is True


def test_callback_rejects_missing_or_bad_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "sgn")
    client, slack_module = _setup(tmp_path, monkeypatch)

    async def fake_oauth_access(*a, **k):
        raise AssertionError("must not exchange code without valid state")

    monkeypatch.setattr(slack_module._web, "oauth_access", fake_oauth_access)
    assert client.get("/slack/oauth/callback?code=c").status_code == 400
    assert client.get("/slack/oauth/callback?code=c&state=forged.sig").status_code == 400


def test_callback_rejects_expired_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "sgn")
    client, slack_module = _setup(tmp_path, monkeypatch)
    from slackbot.verify import make_state

    stale = make_state("sgn", now=1000.0)  # long past

    async def fake_oauth_access(*a, **k):
        raise AssertionError("must not exchange an expired state")

    monkeypatch.setattr(slack_module._web, "oauth_access", fake_oauth_access)
    assert client.get(f"/slack/oauth/callback?code=c&state={stale}").status_code == 400
