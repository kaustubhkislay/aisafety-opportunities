import discord

from backend.store import RawStore
from bot.channel_config import ChannelConfig
from bot.config import load_config
from bot.coordinator import Ingestor
from bot.forwarder import Forwarder


def build_client(config: dict) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    store = RawStore(config["raw_db_path"])
    store.init_db()
    forwarder = Forwarder(config["ingest_base_url"], config["ingest_secret"])
    channel_config = ChannelConfig.from_json(config.get("channel_config_path", "channels.json"))
    ingestor = Ingestor(store, forwarder, channel_config.channel_default)

    @client.event
    async def on_ready():
        channels = [
            channel
            for guild in client.guilds
            for channel in guild.text_channels
        ]
        await ingestor.run_startup(channels)

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        await ingestor.handle_live(message)

    return client


def main() -> None:
    config = load_config()
    client = build_client(config)
    client.run(config["discord_token"])


if __name__ == "__main__":
    main()
