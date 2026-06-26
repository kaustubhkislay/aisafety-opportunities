import discord

from bot.backfill import backfill_channel
from bot.messages import message_to_payload


class Ingestor:
    """Coordinates backfill and live ingestion. Live messages that arrive
    while the initial per-channel backfill is still running are buffered so
    none are lost and no channel's cursor is advanced past un-backfilled
    history; they are drained once backfill completes."""

    def __init__(self, store, forwarder):
        self.store = store
        self.forwarder = forwarder
        self._ready = False
        self._buffer = []

    async def _forward(self, message) -> None:
        payload = message_to_payload(message)
        status = await self.forwarder.forward(payload)
        if status // 100 == 2:
            self.store.set_cursor(payload["channel_id"], payload["message_id"])

    async def handle_live(self, message) -> None:
        if not self._ready:
            self._buffer.append(message)
            return
        await self._forward(message)

    async def run_startup(self, channels) -> None:
        for channel in channels:
            try:
                await backfill_channel(channel, self.store, self.forwarder)
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
