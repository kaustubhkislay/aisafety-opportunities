def _content(message) -> str:
    # Discord "forwards" carry empty .content; the forwarded text lives in
    # message_snapshots. Prefer real content, fall back to the snapshot.
    if message.content:
        return message.content
    for snapshot in getattr(message, "message_snapshots", None) or []:
        if getattr(snapshot, "content", ""):
            return snapshot.content
    return message.content or ""


def message_to_payload(message) -> dict:
    return {
        "server_id": str(message.guild.id),
        "server_name": str(getattr(message.guild, "name", "") or ""),
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "content": _content(message),
        "created_at": message.created_at.isoformat(),
    }
