from slackbot.events import Backfill, Drop, Ingest, Purge, Retract, translate

TEAM = "T1"
NAME = "AI Safety Workspace"
BOT = "U99"


def _translate(event):
    return translate(event, team_id=TEAM, team_name=NAME, bot_user_id=BOT)


def test_plain_message_becomes_ingest():
    action = _translate({
        "type": "message",
        "channel": "C1",
        "user": "U42",
        "text": "Fellowship open, apply: https://example.org",
        "ts": "1751852400.000200",
    })
    assert isinstance(action, Ingest)
    assert action.msg == {
        "server_id": "slack:T1",
        "server_name": NAME,
        "channel_id": "C1",
        "message_id": "slack:T1:C1:1751852400.000200",
        "author_id": "U42",
        "content": "Fellowship open, apply: https://example.org",
        "created_at": "2025-07-07T01:40:00+00:00",
    }


def test_excluded_message_dropped_with_reason():
    action = _translate({
        "type": "message",
        "channel": "C1",
        "user": "U42",
        "text": "[private] internal fellowship",
        "ts": "1.0",
    })
    assert isinstance(action, Drop)
    assert action.reason == "tag:[private]"


def test_bot_message_dropped():
    action = _translate({
        "type": "message",
        "channel": "C1",
        "bot_id": "B7",
        "text": "automated post",
        "ts": "1.0",
    })
    assert isinstance(action, Drop)


def test_edit_adding_private_tag_retracts():
    action = _translate({
        "type": "message",
        "subtype": "message_changed",
        "channel": "C1",
        "message": {"text": "now [private] please", "ts": "1751852400.000200", "user": "U42"},
    })
    assert action == Retract(message_id="slack:T1:C1:1751852400.000200")


def test_edit_without_tag_ignored():
    action = _translate({
        "type": "message",
        "subtype": "message_changed",
        "channel": "C1",
        "message": {"text": "just fixing a typo", "ts": "1.0", "user": "U42"},
    })
    assert action is None


def test_other_subtype_dropped():
    action = _translate({
        "type": "message",
        "subtype": "channel_join",
        "channel": "C1",
        "ts": "1.0",
    })
    assert isinstance(action, Drop)


def test_lock_reaction_retracts():
    action = _translate({
        "type": "reaction_added",
        "reaction": "lock",
        "item": {"type": "message", "channel": "C1", "ts": "1751852400.000200"},
    })
    assert action == Retract(message_id="slack:T1:C1:1751852400.000200")


def test_other_reaction_ignored():
    action = _translate({
        "type": "reaction_added",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C1", "ts": "1.0"},
    })
    assert action is None


def test_bot_invited_triggers_backfill():
    action = _translate({
        "type": "member_joined_channel",
        "user": BOT,
        "channel": "C1",
    })
    assert action == Backfill(channel_id="C1")


def test_human_join_ignored():
    action = _translate({
        "type": "member_joined_channel",
        "user": "U42",
        "channel": "C1",
    })
    assert action is None


def test_app_uninstalled_purges():
    assert _translate({"type": "app_uninstalled"}) == Purge(server_id="slack:T1")


def test_tokens_revoked_purges():
    assert _translate({"type": "tokens_revoked"}) == Purge(server_id="slack:T1")


def test_unknown_event_ignored():
    assert _translate({"type": "team_join"}) is None
