import logging

import discord

from bot.exclusion import should_exclude
from bot.messages import message_to_payload

log = logging.getLogger("backfill")


async def backfill_channel(
    channel, store, forwarder, channel_default: str = "public", oldest_snowflake=None,
) -> int:
    channel_id = str(channel.id)
    last_id = store.get_cursor(channel_id)
    # Start from the cursor or the age cutoff, whichever is more recent —
    # messages older than the allowed window never ingest.
    after_id = max(int(last_id) if last_id else 0, oldest_snowflake or 0)
    after = discord.Object(id=after_id) if after_id else None

    count = 0
    async for message in channel.history(after=after):
        payload = message_to_payload(message)
        excluded, reason = should_exclude(payload["content"], channel_default)
        if excluded:
            log.info(
                "edge-excluded message %s in channel %s (%s); not transmitted",
                payload["message_id"], channel_id, reason,
            )
            store.set_cursor(channel_id, payload["message_id"], payload["server_id"])  # seen + dropped
            continue
        status = await forwarder.forward(payload)
        if status // 100 != 2:
            break  # leave cursor at last success; retry on next reconnect
        store.set_cursor(channel_id, payload["message_id"], payload["server_id"])
        count += 1
    return count
