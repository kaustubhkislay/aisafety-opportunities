import discord

from bot.messages import message_to_payload


async def backfill_channel(channel, store, forwarder) -> int:
    channel_id = str(channel.id)
    last_id = store.get_cursor(channel_id)
    after = discord.Object(id=int(last_id)) if last_id else None

    count = 0
    async for message in channel.history(after=after):
        payload = message_to_payload(message)
        await forwarder.forward(payload)
        store.set_cursor(channel_id, payload["message_id"])
        count += 1
    return count
