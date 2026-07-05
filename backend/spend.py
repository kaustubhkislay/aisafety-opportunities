"""LLM spend cap (T6.4).

A per-period guard on LLM extraction calls so a flood of messages (or a bug)
cannot run up an unbounded bill. The worker charges the guard once per
extraction attempt; once the period's budget is spent, extraction refuses and
rows stay unprocessed until the next period.

The counter is in-memory: a worker restart resets it. That is acceptable for a
safety cap (it bounds the steady state, not exact accounting).
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger("spend")


class SpendCapExceeded(Exception):
    """Raised instead of calling the LLM once the period's cap is spent."""


def _utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class SpendGuard:
    """Counts LLM calls per period and refuses once ``cap`` is reached.

    ``clock`` returns the current period key (default: UTC date); when it
    changes, the counter resets.
    """

    def __init__(self, cap: int, clock=_utc_day):
        self.cap = cap
        self._clock = clock
        self._period = None
        self._count = 0

    def try_acquire(self) -> bool:
        period = self._clock()
        if period != self._period:
            self._period = period
            self._count = 0
        if self._count >= self.cap:
            return False
        self._count += 1
        return True

    @classmethod
    def from_env(cls, env) -> "SpendGuard | None":
        """Build from ``LLM_DAILY_CALL_CAP``; unset or 0 disables the guard."""
        cap = int(env.get("LLM_DAILY_CALL_CAP", "0"))
        return cls(cap) if cap > 0 else None
