"""Ingestion scope: which channels, how far back.

Opportunities are pulled solely from channels whose name contains
``opportunities`` (configurable via ``CHANNEL_NAME_FILTER``), and backfill
never reaches further back than ``MAX_MESSAGE_AGE_DAYS`` (default 14) — stale
announcements aren't worth publishing.
"""

from datetime import datetime, timedelta, timezone

_DISCORD_EPOCH = datetime(2015, 1, 1, tzinfo=timezone.utc)


def is_ingest_channel(name: str | None, needle: str = "opportunities") -> bool:
    return needle in (name or "").lower()


def oldest_allowed_snowflake(now: datetime, max_age_days: int) -> int:
    """Discord snowflake for the oldest message the backfill may ingest."""
    cutoff = now - timedelta(days=max_age_days)
    ms = int((cutoff - _DISCORD_EPOCH) / timedelta(milliseconds=1))
    return ms << 22
