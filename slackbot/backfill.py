"""Per-channel history backfill, triggered when the bot is invited.

Scope check first (member AND name filter) so an invite to #general reads
nothing. History is paged oldest-bounded to the 14-day window and each
message goes through the same translate/exclusion path as live events.
"""

import logging
from datetime import datetime, timedelta

from bot.scope import is_ingest_channel
from slackbot.events import Ingest, translate

logger = logging.getLogger(__name__)


async def backfill_channel(
    web,
    token: str,
    team_id: str,
    team_name: str,
    bot_user_id: str,
    channel_id: str,
    store,
    now: datetime,
    max_age_days: int = 14,
) -> int:
    info = await web.conversations_info(token, channel_id)
    channel = info.get("channel") or {}
    if not channel.get("is_member") or not is_ingest_channel(channel.get("name")):
        logger.info("slack backfill skipped channel=%s (out of scope)", channel_id)
        return 0

    oldest = str(int((now - timedelta(days=max_age_days)).timestamp()))
    ingested = 0
    cursor: str | None = None
    while True:
        page = await web.conversations_history(token, channel_id, oldest=oldest, cursor=cursor)
        for raw in page.get("messages", []):
            event = dict(raw)
            event.setdefault("channel", channel_id)
            action = translate(event, team_id=team_id, team_name=team_name,
                               bot_user_id=bot_user_id)
            if isinstance(action, Ingest) and store.insert_message(action.msg):
                ingested += 1
        cursor = (page.get("response_metadata") or {}).get("next_cursor") or None
        if not cursor:
            break
    logger.info("slack backfill channel=%s ingested=%d", channel_id, ingested)
    return ingested
