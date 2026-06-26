def message_to_payload(message) -> dict:
    return {
        "server_id": str(message.guild.id),
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }
