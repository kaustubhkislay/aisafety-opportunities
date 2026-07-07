"""Pure translators from Slack Events API payloads to pipeline actions.

Edge exclusion runs here — an excluded message becomes ``Drop`` and is never
stored. Slack has no private-by-default channel config in v1, so the channel
default passed to ``should_exclude`` is always "public".
"""

from dataclasses import dataclass

from bot.exclusion import should_exclude
from slackbot.ids import message_id, server_id, ts_to_iso


@dataclass(frozen=True)
class Ingest:
    msg: dict


@dataclass(frozen=True)
class Retract:
    message_id: str


@dataclass(frozen=True)
class Backfill:
    channel_id: str


@dataclass(frozen=True)
class Purge:
    server_id: str


@dataclass(frozen=True)
class Drop:
    reason: str


def translate(
    event: dict, team_id: str, team_name: str, bot_user_id: str
) -> Ingest | Retract | Backfill | Purge | Drop | None:
    etype = event.get("type")

    if etype == "message":
        subtype = event.get("subtype")
        if subtype == "message_changed":
            inner = event.get("message") or {}
            excluded, _ = should_exclude(inner.get("text"), "public")
            if excluded:
                return Retract(
                    message_id=message_id(team_id, event.get("channel", ""), inner.get("ts", ""))
                )
            return None
        if subtype is not None or event.get("bot_id"):
            return Drop(reason=f"subtype:{subtype or 'bot_message'}")
        excluded, reason = should_exclude(event.get("text"), "public")
        if excluded:
            return Drop(reason=reason)
        return Ingest(
            msg={
                "server_id": server_id(team_id),
                "server_name": team_name,
                "channel_id": event.get("channel", ""),
                "message_id": message_id(team_id, event.get("channel", ""), event.get("ts", "")),
                "author_id": event.get("user", ""),
                "content": event.get("text", ""),
                "created_at": ts_to_iso(event.get("ts", "0")),
            }
        )

    if etype == "reaction_added":
        if event.get("reaction") != "lock":
            return None
        item = event.get("item") or {}
        if item.get("type") != "message":
            return None
        return Retract(
            message_id=message_id(team_id, item.get("channel", ""), item.get("ts", ""))
        )

    if etype == "member_joined_channel":
        if event.get("user") == bot_user_id:
            return Backfill(channel_id=event.get("channel", ""))
        return None

    if etype in ("app_uninstalled", "tokens_revoked"):
        return Purge(server_id=server_id(team_id))

    return None
