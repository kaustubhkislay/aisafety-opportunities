import logging

import discord

from bot.backfill import backfill_channel
from bot.exclusion import should_exclude
from bot.messages import message_to_payload

log = logging.getLogger("ingestor")


def _public_default(server_id: str, channel_id: str) -> str:
    return "public"


class Ingestor:
    """Coordinates backfill and live ingestion. Live messages that arrive
    while the initial per-channel backfill is still running are buffered so
    none are lost and no channel's cursor is advanced past un-backfilled
    history; they are drained once backfill completes.

    ``channel_default_fn(server_id, channel_id) -> "public" | "private"`` supplies
    each channel's privacy default for edge exclusion (T3.2 wires real config;
    default is public)."""

    def __init__(self, store, forwarder, channel_default_fn=_public_default):
        self.store = store
        self.forwarder = forwarder
        self.channel_default_fn = channel_default_fn
        self._ready = False
        self._buffer = []
        self.oldest_snowflake = None  # set by the client from MAX_MESSAGE_AGE_DAYS

    async def _forward(self, message) -> None:
        payload = message_to_payload(message)
        default = self.channel_default_fn(payload["server_id"], payload["channel_id"])
        excluded, reason = should_exclude(payload["content"], default)
        if excluded:
            log.info(
                "edge-excluded message %s in channel %s (%s); not transmitted",
                payload["message_id"], payload["channel_id"], reason,
            )
            return
        status = await self.forwarder.forward(payload)
        if status // 100 == 2:
            self.store.set_cursor(payload["channel_id"], payload["message_id"], payload["server_id"])

    async def handle_live(self, message) -> None:
        if not self._ready:
            self._buffer.append(message)
            return
        await self._forward(message)

    async def run_startup(self, channels) -> None:
        for channel in channels:
            guild = getattr(channel, "guild", None)
            server_id = str(guild.id) if guild is not None else ""
            default = self.channel_default_fn(server_id, str(channel.id))
            try:
                await backfill_channel(
                    channel, self.store, self.forwarder, channel_default=default,
                    oldest_snowflake=self.oldest_snowflake,
                )
            except discord.Forbidden:
                continue  # not authorized to read this channel
        # Drain live messages buffered during backfill. Loop because new
        # messages can arrive during the awaits in the drain itself; once the
        # buffer is empty we flip _ready with no await in between, so nothing
        # can slip past.
        while self._buffer:
            buffered, self._buffer = self._buffer, []
            for message in buffered:
                await self._forward(message)
        self._ready = True
