"""Edge exclusion (Slice 5).

The bot's strongest privacy guarantee: messages an owner marks private — or any
message in a channel an owner set private-by-default — are dropped *in the bot,
before any network transmit*, so excluded content never leaves the server.

`should_exclude` is pure; the transmit paths (`bot.coordinator.Ingestor._forward`
and `bot.backfill.backfill_channel`) call it before forwarding and log every drop.
"""

import re

# Documented exclusion vocabulary. Authors add any of these to opt a message out.
_TAGS = ("[private]", "school-specific", "internal", "do-not-share")

# Match each tag as a whole token (so "internal" does not fire inside
# "internationally"). Hyphens count as part of a token so "do-not-share" matches
# as a unit; the bracketed literal is matched verbatim.
_PATTERNS = [
    (re.compile(r"(?<![\w-])" + re.escape(tag) + r"(?![\w-])", re.IGNORECASE), tag)
    for tag in _TAGS
]


def should_exclude(content: str | None, channel_default: str) -> tuple[bool, str]:
    """Return ``(excluded, reason)``.

    Excluded when the content carries an exclusion tag, or when the channel is
    private-by-default. ``reason`` is ``"tag:<tag>"``, ``"private-channel"``, or
    ``"ok"`` when not excluded.
    """
    text = content or ""
    for pattern, tag in _PATTERNS:
        if pattern.search(text):
            return (True, f"tag:{tag}")
    if channel_default == "private":
        return (True, "private-channel")
    return (False, "ok")
