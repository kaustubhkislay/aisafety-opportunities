from slackbot.tokens import TokenStore


def _store(tmp_path) -> TokenStore:
    s = TokenStore(str(tmp_path / "slack_tokens.db"))
    s.init_db()
    return s


def test_save_and_get(tmp_path):
    s = _store(tmp_path)
    s.save("T1", "AI Safety Workspace", "xoxb-abc", "U99")
    row = s.get("T1")
    assert row == {
        "team_id": "T1",
        "team_name": "AI Safety Workspace",
        "bot_token": "xoxb-abc",
        "bot_user_id": "U99",
    }


def test_get_missing_returns_none(tmp_path):
    assert _store(tmp_path).get("T404") is None


def test_save_is_upsert(tmp_path):
    s = _store(tmp_path)
    s.save("T1", "Old Name", "xoxb-old", "U99")
    s.save("T1", "New Name", "xoxb-new", "U99")
    row = s.get("T1")
    assert row["team_name"] == "New Name"
    assert row["bot_token"] == "xoxb-new"


def test_delete(tmp_path):
    s = _store(tmp_path)
    s.save("T1", "W", "xoxb-abc", "U99")
    assert s.delete("T1") is True
    assert s.get("T1") is None
    assert s.delete("T1") is False
