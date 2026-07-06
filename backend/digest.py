"""Email digest (Slice 6 / T4.1).

Builds a periodic digest of currently-open opportunities and sends one email per
active subscriber, each with a signed (HMAC) unsubscribe link. The actual sending
service (Resend/Buttondown) is injected as a ``sender`` callable — wired in T4.2;
here everything is pure and testable.
"""

import base64
import hashlib
import hmac
import logging
import os
import re
from datetime import date
from html import escape

from backend.status_job import derive_status
from backend.subscribers import SubscriberStore

log = logging.getLogger("digest")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


# --- unsubscribe tokens (HMAC-signed, stateless) --------------------------

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def make_token(email: str, secret: str) -> str:
    email = email.strip().lower()
    sig = hmac.new(secret.encode(), email.encode(), hashlib.sha256).digest()
    return f"{_b64(email.encode())}.{_b64(sig)}"


def verify_token(token: str, secret: str) -> str | None:
    try:
        email_part, sig_part = token.split(".", 1)
        email = _unb64(email_part).decode()
        expected = hmac.new(secret.encode(), email.encode(), hashlib.sha256).digest()
        if hmac.compare_digest(_unb64(sig_part), expected):
            return email
    except Exception:  # noqa: BLE001 - any malformed/garbage token is simply invalid
        return None
    return None


# --- digest body -----------------------------------------------------------

def build_digest(opportunities: list[dict], unsubscribe_url: str) -> dict:
    """Compose subject/html/text from already-filtered, already-sorted opportunities."""
    subject = (
        f"AI Safety Opportunities — {len(opportunities)} open"
        if opportunities else "AI Safety Opportunities — digest"
    )

    if opportunities:
        html_items = "".join(_html_item(o) for o in opportunities)
        text_items = "\n".join(_text_item(o) for o in opportunities)
    else:
        html_items = "<p>No new opportunities this period.</p>"
        text_items = "No new opportunities this period."

    html = (
        f"<h1>AI Safety Opportunities</h1>{html_items}"
        f'<p><a href="{escape(unsubscribe_url)}">Unsubscribe</a></p>'
    )
    text = f"AI Safety Opportunities\n\n{text_items}\n\nUnsubscribe: {unsubscribe_url}\n"
    return {"subject": subject, "html": html, "text": text}


def _html_item(o: dict) -> str:
    title = escape(o.get("title") or "Untitled")
    org = escape(o.get("org") or "")
    deadline = escape(o.get("deadline") or "no deadline")
    link = o.get("link")
    heading = f'<a href="{escape(link)}">{title}</a>' if link else title
    return f"<p><strong>{heading}</strong> — {org} (closes {deadline})</p>"


def _text_item(o: dict) -> str:
    title = o.get("title") or "Untitled"
    org = o.get("org") or ""
    deadline = o.get("deadline") or "no deadline"
    link = o.get("link") or ""
    return f"- {title} — {org} (closes {deadline}) {link}".rstrip()


def _sort_key(o: dict):
    # deadline asc (none last), then date_seen desc
    deadline = o.get("deadline") or "9999-12-31"
    date_seen = o.get("date_seen") or ""
    return (deadline, _Reversed(date_seen))


class _Reversed:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


def run_digest(
    subscriber_store,
    opportunities: list[dict],
    sender,
    *,
    secret: str,
    unsubscribe_base: str,
    today: date,
    since: str | None = None,
    skip_when_empty: bool = False,
) -> int:
    """Send the digest to every active subscriber. Returns the number sent."""
    items = [o for o in opportunities if derive_status(o.get("deadline"), today) != "expired"]
    if since is not None:
        items = [o for o in items if (o.get("date_seen") or "") >= since]
    items.sort(key=_sort_key)
    if skip_when_empty and not items:
        log.info("digest: nothing new since %s — skipping send", since)
        return 0

    count = 0
    for email in subscriber_store.active_emails():
        url = f"{unsubscribe_base}?token={make_token(email, secret)}"
        digest = build_digest(items, url)
        sender(email, digest["subject"], digest["html"], digest["text"])
        count += 1
    log.info("digest: sent to %d subscriber(s), %d item(s)", count, len(items))
    return count


def _log_sender(email: str, subject: str, html: str, text: str) -> None:
    # Fallback sender when no email provider is configured (dev / dry runs).
    log.info("would send digest to %s: %s", email, subject)


# --- Resend sender (T4.2) ---------------------------------------------------

def make_resend_sender(api_key: str, from_address: str, post=None):
    """Return a ``sender(email, subject, html, text)`` backed by the Resend API."""
    if post is None:
        import httpx

        post = httpx.post

    def sender(email: str, subject: str, html: str, text: str) -> None:
        res = post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": f"AI Safety Opportunities <{from_address}>",
                "to": [email],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=30,
        )
        if not 200 <= res.status_code < 300:
            raise RuntimeError(f"resend send failed ({res.status_code}): {res.text}")

    return sender


def resend_sender_from_env(env):
    """Build the Resend sender from ``RESEND_API_KEY`` + ``DIGEST_FROM_ADDRESS``;
    ``None`` when either is missing (caller falls back to the log sender)."""
    api_key = env.get("RESEND_API_KEY")
    from_address = env.get("DIGEST_FROM_ADDRESS")
    if not api_key or not from_address:
        return None
    return make_resend_sender(api_key, from_address)


def main(sender=None) -> None:
    """Scheduled entrypoint (cron, wired in M6). Reads opportunities + subscribers
    and sends the digest via Resend when configured, else the log sender."""
    if sender is None:
        sender = resend_sender_from_env(os.environ)
        if sender is None:
            log.warning(
                "RESEND_API_KEY / DIGEST_FROM_ADDRESS not set — digest will only be logged"
            )
            sender = _log_sender
    logging.basicConfig(level=logging.INFO)
    from backend.airtable import AirtableStore, backend_from_env

    airtable = AirtableStore(backend_from_env())
    opportunities = [record.get("fields", {}) for record in airtable.backend.all()]

    subscribers = SubscriberStore(os.environ.get("SUBSCRIBER_DB_PATH", "subscribers.db"))
    subscribers.init_db()

    base = os.environ.get("BACKEND_URL", "http://localhost:3000").rstrip("/") + "/unsubscribe"
    # Daily digest: only opportunities first seen since yesterday, and no
    # email at all on days with nothing new.
    from datetime import timedelta

    run_digest(
        subscribers,
        opportunities,
        sender,
        secret=os.environ["UNSUBSCRIBE_SECRET"],
        unsubscribe_base=base,
        today=date.today(),
        since=(date.today() - timedelta(days=1)).isoformat(),
        skip_when_empty=True,
    )


if __name__ == "__main__":
    main()
