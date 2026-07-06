import logging

import discord

from backend.store import RawStore
from bot.channel_config import ChannelConfig
from bot.config import load_config
from bot.coordinator import Ingestor
from bot.forwarder import Forwarder
from bot.retraction import is_retraction_edit, is_retraction_reaction
from bot.scope import is_ingest_channel, oldest_allowed_snowflake


def build_client(config: dict) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    store = RawStore(config["raw_db_path"])
    store.init_db()
    forwarder = Forwarder(config["ingest_base_url"], config["ingest_secret"])
    channel_config = ChannelConfig.from_json(config.get("channel_config_path", "channels.json"))
    ingestor = Ingestor(store, forwarder, channel_config.channel_default)
    needle = config.get("channel_name_filter", "opportunities")

    from datetime import datetime, timezone

    ingestor.oldest_snowflake = oldest_allowed_snowflake(
        datetime.now(timezone.utc), config.get("max_message_age_days", 14)
    )

    @client.event
    async def on_ready():
        channels = [
            channel
            for guild in client.guilds
            for channel in guild.text_channels
            if is_ingest_channel(channel.name, needle)
        ]
        await ingestor.run_startup(channels)

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        if not is_ingest_channel(getattr(message.channel, "name", None), needle):
            return
        await ingestor.handle_live(message)

    @client.event
    async def on_raw_reaction_add(payload):
        # Raw event: fires even for messages not in the bot's cache.
        if is_retraction_reaction(str(payload.emoji)):
            await forwarder.retract(str(payload.message_id))

    @client.event
    async def on_raw_message_edit(payload):
        content = (payload.data or {}).get("content")
        if is_retraction_edit(content):
            await forwarder.retract(str(payload.message_id))

    @client.event
    async def on_guild_remove(guild):
        # Bot removed from a server -> purge everything ingested from it.
        await forwarder.purge(str(guild.id))

    return client


def main() -> None:
    # INFO so edge-exclusion drops are always visible in production logs —
    # the design invariant is "no silent drop without a log line".
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    client = build_client(config)
    client.run(config["discord_token"], log_handler=None)


if __name__ == "__main__":
    main()
