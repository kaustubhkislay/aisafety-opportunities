"""Per-channel privacy config (Slice 5 / T3.2).

Each authorized channel has a default: ``public`` (forward by default) or
``private`` (fail closed — exclude even untagged messages). Captured at install
(T3.5) and persisted as JSON; here we load it and answer the per-channel lookup
that ``bot.coordinator.Ingestor`` / ``bot.backfill`` use for edge exclusion.
"""

import json
import logging

log = logging.getLogger("channel_config")

_VALID = {"public", "private"}


class ChannelConfig:
    def __init__(self, overrides: dict | None = None, fallback: str = "public"):
        # overrides: {(server_id, channel_id): "public" | "private"}
        self._overrides = {
            (str(s), str(c)): v for (s, c), v in (overrides or {}).items()
        }
        self.fallback = fallback if fallback in _VALID else "public"

    def channel_default(self, server_id, channel_id) -> str:
        return self._overrides.get((str(server_id), str(channel_id)), self.fallback)

    @classmethod
    def from_json(cls, path: str) -> "ChannelConfig":
        """Load config from JSON: ``{"fallback": "...", "channels": {"sid:cid": "private"}}``.

        A missing file means no overrides (everything public) — the bot still runs.
        """
        try:
            with open(path) as f:
                data = json.load(f)
        except FileNotFoundError:
            log.info("no channel config at %s; defaulting all channels public", path)
            return cls()

        fallback = data.get("fallback", "public")
        overrides: dict = {}
        for key, value in data.get("channels", {}).items():
            if value not in _VALID:
                log.warning("ignoring channel %s with invalid default %r", key, value)
                continue
            sid, _, cid = key.partition(":")
            overrides[(sid, cid)] = value
        return cls(overrides, fallback)
