"""Cached channel-scope check for the live event path.

Consent = the bot is a member AND the channel name passes the ingest filter.
Cached per channel id (positive and negative) because it gates every live
message; ``invalidate`` is called on fresh invites so re-invites and renames
get re-checked without a process restart.
"""

from bot.scope import is_ingest_channel


class ChannelScope:
    def __init__(self):
        self._cache: dict[str, bool] = {}

    async def in_scope(self, web, token: str, channel_id: str) -> bool:
        cached = self._cache.get(channel_id)
        if cached is None:
            info = await web.conversations_info(token, channel_id)
            channel = info.get("channel") or {}
            cached = bool(channel.get("is_member")) and is_ingest_channel(
                channel.get("name")
            )
            self._cache[channel_id] = cached
        return cached

    def invalidate(self, channel_id: str) -> None:
        self._cache.pop(channel_id, None)
