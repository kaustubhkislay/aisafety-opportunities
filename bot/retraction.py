"""Retraction signals (Slice 5 / T3.3).

After a message has been posted (and possibly published to the site), an owner or
author can pull it back: react with the lock emoji, or edit the message to add the
``[private]`` tag. Either signal tells the backend to delete the corresponding
record from the site. This module only *detects* the signal; the actual delete
call reuses ``bot.forwarder.Forwarder.retract`` (same backend, same secret).
"""

LOCK_EMOJI = "\U0001F512"  # 🔒


def is_retraction_reaction(emoji: str) -> bool:
    return emoji == LOCK_EMOJI


_RETRACTION_TAGS = ("[private]", "[uni-reserved]")


def is_retraction_edit(content: str | None) -> bool:
    lowered = (content or "").lower()
    return any(tag in lowered for tag in _RETRACTION_TAGS)
