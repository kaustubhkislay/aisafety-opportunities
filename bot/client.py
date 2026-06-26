import discord

from backend.store import RawStore
from bot.backfill import backfill_channel
from bot.config import load_config
from bot.forwarder import Forwarder
from bot.messages import message_to_payload


def build_client(config: dict) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    store = RawStore(config["raw_db_path"])
    store.init_db()
    forwarder = Forwarder(config["ingest_base_url"], config["ingest_secret"])

    @client.event
    async def on_ready():
        for guild in client.guilds:
            for channel in guild.text_channels:
                try:
                    await backfill_channel(channel, store, forwarder)
                except discord.Forbidden:
                    continue  # not authorized to read this channel

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        payload = message_to_payload(message)
        await forwarder.forward(payload)
        store.set_cursor(payload["channel_id"], payload["message_id"])

    return client


def main() -> None:
    config = load_config()
    client = build_client(config)
    client.run(config["discord_token"])


if __name__ == "__main__":
    main()
