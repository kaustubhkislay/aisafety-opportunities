"""Slack request verification.

Slack signs each request: ``v0=`` + HMAC-SHA256 of ``v0:<timestamp>:<body>``
with the app's signing secret. Requests older than ±5 minutes are rejected to
block replays. https://api.slack.com/authentication/verifying-requests-from-slack
"""

import hashlib
import hmac

_MAX_SKEW_SECONDS = 60 * 5


def verify_slack_signature(
    signing_secret: str, timestamp: str, body: bytes, signature: str, now: float
) -> bool:
    if not signature or not signing_secret:
        return False
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(now - ts) > _MAX_SKEW_SECONDS:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# --- OAuth state (CSRF protection for the install flow) ----------------------

_STATE_MAX_AGE = 60 * 10


def make_state(signing_secret: str, now: float) -> str:
    """Signed, timestamped OAuth ``state``: ``<ts>.<hmac(ts)>``."""
    ts = str(int(now))
    sig = hmac.new(signing_secret.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def verify_state(signing_secret: str, state: str, now: float) -> bool:
    if not state or not signing_secret:
        return False
    ts, _, sig = state.partition(".")
    expected = hmac.new(signing_secret.encode(), ts.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        age = now - float(ts)
    except ValueError:
        return False
    return 0 <= age <= _STATE_MAX_AGE
