from slackbot.channels import ChannelScope


class FakeWeb:
    def __init__(self, channel: dict):
        self.channel = channel
        self.calls = 0

    async def conversations_info(self, token, channel):
        self.calls += 1
        return {"ok": True, "channel": self.channel}


async def test_in_scope_member_with_matching_name():
    web = FakeWeb({"id": "C1", "name": "ai-opportunities", "is_member": True})
    scope = ChannelScope()
    assert await scope.in_scope(web, "xoxb-1", "C1") is True


async def test_out_of_scope_wrong_name():
    web = FakeWeb({"id": "C2", "name": "general", "is_member": True})
    scope = ChannelScope()
    assert await scope.in_scope(web, "xoxb-1", "C2") is False


async def test_out_of_scope_not_member():
    web = FakeWeb({"id": "C3", "name": "opportunities", "is_member": False})
    scope = ChannelScope()
    assert await scope.in_scope(web, "xoxb-1", "C3") is False


async def test_result_is_cached():
    web = FakeWeb({"id": "C1", "name": "opportunities", "is_member": True})
    scope = ChannelScope()
    await scope.in_scope(web, "xoxb-1", "C1")
    await scope.in_scope(web, "xoxb-1", "C1")
    assert web.calls == 1


async def test_invalidate_forces_recheck():
    web = FakeWeb({"id": "C1", "name": "renamed-opportunities", "is_member": True})
    scope = ChannelScope()
    await scope.in_scope(web, "xoxb-1", "C1")
    scope.invalidate("C1")
    await scope.in_scope(web, "xoxb-1", "C1")
    assert web.calls == 2
