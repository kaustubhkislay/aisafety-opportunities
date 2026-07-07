import hashlib
import hmac

from slackbot.verify import verify_slack_signature

SECRET = "8f742231b10e8888abcd99yyyzzz85a5"
NOW = 1_751_900_000.0


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode() + b":" + body
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def test_valid_signature_accepted():
    ts = str(int(NOW))
    body = b'{"type":"url_verification"}'
    sig = _sign(SECRET, ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig, now=NOW) is True


def test_wrong_secret_rejected():
    ts = str(int(NOW))
    body = b"{}"
    sig = _sign("other-secret", ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig, now=NOW) is False


def test_tampered_body_rejected():
    ts = str(int(NOW))
    sig = _sign(SECRET, ts, b"original")
    assert verify_slack_signature(SECRET, ts, b"tampered", sig, now=NOW) is False


def test_stale_timestamp_rejected():
    ts = str(int(NOW) - 60 * 6)  # 6 minutes old: replay guard is ±5 minutes
    body = b"{}"
    sig = _sign(SECRET, ts, body)
    assert verify_slack_signature(SECRET, ts, body, sig, now=NOW) is False


def test_garbage_timestamp_rejected():
    assert verify_slack_signature(SECRET, "not-a-number", b"{}", "v0=abc", now=NOW) is False


def test_missing_signature_rejected():
    ts = str(int(NOW))
    assert verify_slack_signature(SECRET, ts, b"{}", "", now=NOW) is False


def test_state_round_trip_and_expiry():
    from slackbot.verify import make_state, verify_state

    state = make_state("secret", now=1_000_000.0)
    assert verify_state("secret", state, now=1_000_000.0 + 60) is True
    assert verify_state("secret", state, now=1_000_000.0 + 601) is False  # >10 min
    assert verify_state("other", state, now=1_000_000.0) is False
    assert verify_state("secret", "garbage", now=1_000_000.0) is False
    assert verify_state("secret", "", now=1_000_000.0) is False
