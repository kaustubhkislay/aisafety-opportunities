import os


def load_config() -> dict:
    return {
        "discord_token": os.environ["DISCORD_BOT_TOKEN"],
        "ingest_base_url": os.environ.get("INGEST_BASE_URL", "http://localhost:3000"),
        "ingest_secret": os.environ["INGEST_SHARED_SECRET"],
        "raw_db_path": os.environ.get("RAW_DB_PATH", "raw.db"),
        "channel_config_path": os.environ.get("CHANNEL_CONFIG_PATH", "channels.json"),
    }
