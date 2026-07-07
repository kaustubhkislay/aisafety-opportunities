"""Slack → pipeline identity mapping.

Slack ``ts`` values are unique only per channel, and must not collide with
Discord snowflakes in the shared raw store — hence the composite, prefixed ids.
"""

from datetime import datetime, timezone


def server_id(team_id: str) -> str:
    return f"slack:{team_id}"


def message_id(team_id: str, channel_id: str, ts: str) -> str:
    return f"slack:{team_id}:{channel_id}:{ts}"


def ts_to_iso(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds")
