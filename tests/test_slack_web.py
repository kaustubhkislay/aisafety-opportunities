import httpx
import pytest

from slackbot.web import SlackApiError, SlackWeb


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_oauth_access_posts_form():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True, "access_token": "xoxb-1",
                                         "team": {"id": "T1", "name": "W"},
                                         "bot_user_id": "U99"})

    web = SlackWeb(client=_client(handler))
    data = await web.oauth_access("cid", "csec", "thecode", "https://x/cb")
    assert data["access_token"] == "xoxb-1"
    assert seen["url"] == "https://slack.com/api/oauth.v2.access"
    assert "code=thecode" in seen["body"]
    assert "client_id=cid" in seen["body"]


async def test_conversations_info_sends_bearer():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer xoxb-1"
        return httpx.Response(200, json={"ok": True, "channel":
                                         {"id": "C1", "name": "opportunities", "is_member": True}})

    web = SlackWeb(client=_client(handler))
    data = await web.conversations_info("xoxb-1", "C1")
    assert data["channel"]["name"] == "opportunities"


async def test_conversations_history_passes_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["channel"] == "C1"
        assert request.url.params["oldest"] == "123.000"
        assert request.url.params["cursor"] == "abc"
        return httpx.Response(200, json={"ok": True, "messages": []})

    web = SlackWeb(client=_client(handler))
    data = await web.conversations_history("xoxb-1", "C1", oldest="123.000", cursor="abc")
    assert data["messages"] == []


async def test_not_ok_raises_slack_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "channel_not_found"})

    web = SlackWeb(client=_client(handler))
    with pytest.raises(SlackApiError) as exc:
        await web.conversations_info("xoxb-1", "C404")
    assert exc.value.error == "channel_not_found"
