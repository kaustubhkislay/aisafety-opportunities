from datetime import date

from backend.digest import (
    build_digest,
    is_valid_email,
    make_token,
    run_digest,
    verify_token,
)
from backend.subscribers import SubscriberStore

TODAY = date(2026, 6, 27)


# --- email validation ------------------------------------------------------

def test_valid_emails():
    assert is_valid_email("a@b.com")
    assert is_valid_email("first.last+tag@sub.example.org")


def test_invalid_emails():
    for bad in ["", "nope", "a@b", "a@@b.com", "a b@c.com", "@b.com"]:
        assert is_valid_email(bad) is False, bad


# --- unsubscribe token (HMAC) ---------------------------------------------

def test_token_roundtrips():
    token = make_token("a@x.com", "secret")
    assert verify_token(token, "secret") == "a@x.com"


def test_token_rejected_with_wrong_secret():
    token = make_token("a@x.com", "secret")
    assert verify_token(token, "other") is None


def test_token_rejected_when_tampered():
    assert verify_token("not-a-real-token", "secret") is None
    token = make_token("a@x.com", "secret")
    assert verify_token(token + "x", "secret") is None


# --- digest body -----------------------------------------------------------

def test_build_digest_lists_items_and_unsub_link():
    opps = [{
        "title": "ML Fellow", "org": "Redwood", "type": "fellowship",
        "deadline": "2026-08-01", "link": "https://x.org/apply", "date_seen": "2026-06-26",
    }]
    digest = build_digest(opps, "https://site/unsubscribe?token=abc")
    assert digest["subject"]
    assert "ML Fellow" in digest["html"]
    assert "ML Fellow" in digest["text"]
    assert "https://x.org/apply" in digest["html"]
    assert "unsubscribe?token=abc" in digest["html"]
    assert "unsubscribe?token=abc" in digest["text"]


def test_build_digest_escapes_html():
    opps = [{"title": "A & B <x>", "org": "o", "type": "job", "deadline": None,
             "link": None, "date_seen": "2026-06-26"}]
    digest = build_digest(opps, "https://site/u")
    assert "&amp;" in digest["html"] and "&lt;x&gt;" in digest["html"]


def test_build_digest_empty_is_still_valid():
    digest = build_digest([], "https://site/u")
    assert digest["text"]
    assert digest["html"]


# --- run_digest ------------------------------------------------------------

def _opp(title, deadline, date_seen="2026-06-26"):
    return {"title": title, "org": "o", "type": "job", "deadline": deadline,
            "link": "https://x.org", "date_seen": date_seen}


def test_run_digest_sends_each_subscriber_with_their_token(tmp_path):
    subs = SubscriberStore(str(tmp_path / "subs.db"))
    subs.init_db()
    subs.add("a@x.com")
    subs.add("b@x.com")
    sent = []

    def sender(email, subject, html, text):
        sent.append((email, html))

    count = run_digest(
        subs, [_opp("Open Fellowship", "2026-08-01")], sender,
        secret="s", unsubscribe_base="https://site/unsubscribe", today=TODAY,
    )

    assert count == 2
    assert {email for email, _ in sent} == {"a@x.com", "b@x.com"}
    # each email carries that subscriber's own unsubscribe token
    for email, html in sent:
        assert make_token(email, "s") in html


def test_run_digest_excludes_expired_opportunities(tmp_path):
    subs = SubscriberStore(str(tmp_path / "subs.db"))
    subs.init_db()
    subs.add("a@x.com")
    sent = []

    def sender(email, subject, html, text):
        sent.append(html)

    run_digest(
        subs,
        [_opp("Past", "2026-06-01"), _opp("Future", "2026-08-01")],
        sender, secret="s", unsubscribe_base="https://site/u", today=TODAY,
    )

    assert "Future" in sent[0]
    assert "Past" not in sent[0]


def test_run_digest_filters_by_since(tmp_path):
    subs = SubscriberStore(str(tmp_path / "subs.db"))
    subs.init_db()
    subs.add("a@x.com")
    sent = []

    def sender(email, subject, html, text):
        sent.append(html)

    run_digest(
        subs,
        [_opp("Old", "2026-08-01", date_seen="2026-06-20"),
         _opp("New", "2026-08-01", date_seen="2026-06-26")],
        sender, secret="s", unsubscribe_base="https://site/u", today=TODAY,
        since="2026-06-25",
    )

    assert "New" in sent[0]
    assert "Old" not in sent[0]


# --- Resend sender (T4.2) ---------------------------------------------------

from backend.digest import make_resend_sender, resend_sender_from_env


class FakeResponse:
    def __init__(self, status_code, body=""):
        self.status_code = status_code
        self.text = body


def test_resend_sender_posts_email():
    calls = []

    def post(url, *, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse(200)

    sender = make_resend_sender("re_key", "digest@aisopportunities.com", post=post)
    sender("a@x.com", "Subject", "<p>hi</p>", "hi")

    url, headers, payload, _timeout = calls[0]
    assert url == "https://api.resend.com/emails"
    assert headers["Authorization"] == "Bearer re_key"
    assert payload == {
        "from": "AI Safety Opportunities <digest@aisopportunities.com>",
        "to": ["a@x.com"],
        "subject": "Subject",
        "html": "<p>hi</p>",
        "text": "hi",
    }


def test_resend_sender_raises_on_error_response():
    import pytest

    sender = make_resend_sender(
        "re_key", "d@x.com", post=lambda url, **kw: FakeResponse(422, "invalid from"),
    )
    with pytest.raises(RuntimeError, match="422"):
        sender("a@x.com", "S", "<p></p>", "t")


def test_resend_sender_from_env_requires_both_vars():
    assert resend_sender_from_env({}) is None
    assert resend_sender_from_env({"RESEND_API_KEY": "re_k"}) is None
    assert resend_sender_from_env({"DIGEST_FROM_ADDRESS": "d@x.com"}) is None
    sender = resend_sender_from_env(
        {"RESEND_API_KEY": "re_k", "DIGEST_FROM_ADDRESS": "d@x.com"},
    )
    assert callable(sender)


def test_skip_when_empty_sends_nothing(tmp_path):
    subs = SubscriberStore(str(tmp_path / "subs.db"))
    subs.init_db()
    subs.add("a@x.com")
    sent = []

    count = run_digest(
        subs,
        [_opp("Old", "2026-08-01", date_seen="2026-06-20")],
        lambda *a: sent.append(a),
        secret="s", unsubscribe_base="https://site/u", today=TODAY,
        since="2026-07-05", skip_when_empty=True,
    )
    assert count == 0
    assert sent == []  # nothing new yesterday -> no email at all


def test_skip_when_empty_still_sends_when_new_items_exist(tmp_path):
    subs = SubscriberStore(str(tmp_path / "subs.db"))
    subs.init_db()
    subs.add("a@x.com")
    sent = []

    count = run_digest(
        subs,
        [_opp("Fresh", "2026-08-01", date_seen="2026-07-05")],
        lambda *a: sent.append(a),
        secret="s", unsubscribe_base="https://site/u", today=TODAY,
        since="2026-07-05", skip_when_empty=True,
    )
    assert count == 1
    assert "Fresh" in sent[0][2]


def test_build_digest_is_branded_html():
    opps = [_opp("ML Fellow", "2026-08-01")]
    digest = build_digest(opps, "https://site/u", site_url="https://aisopportunities.com")
    html = digest["html"]
    assert "#6b46c1" in html  # brand violet
    assert "https://aisopportunities.com" in html  # view-the-board CTA
    assert "max-width" in html  # centered email container
    assert 'style="' in html  # inline styles (email clients ignore stylesheets)


def test_build_digest_items_show_org_deadline_categories():
    opps = [dict(_opp("ML Fellow", "2026-08-01"), org="Redwood", categories=["tech", "gov"])]
    digest = build_digest(opps, "https://site/u")
    html = digest["html"]
    assert "Redwood" in html
    assert "2026-08-01" in html
    assert "tech" in html and "gov" in html


def test_no_deadline_item_omits_closes_line():
    digest = build_digest([_opp("Open Ended", None)], "https://site/u")
    assert "closes" not in digest["html"]
    assert "no deadline" not in digest["html"]


def test_subject_includes_date_to_avoid_threading():
    from datetime import date

    digest = build_digest([_opp("X", "2026-08-01")], "https://site/u", today=date(2026, 7, 7))
    assert digest["subject"] == "AI Safety Opportunities — 1 new · Jul 7"


def test_footer_carries_unique_sent_stamp():
    digest = build_digest(
        [_opp("X", "2026-08-01")], "https://site/u", sent_at="2026-07-07 07:42 UTC",
    )
    assert "Sent 2026-07-07 07:42 UTC" in digest["html"]
    # different stamps -> different bodies, so Gmail can't trim as quoted text
    other = build_digest(
        [_opp("X", "2026-08-01")], "https://site/u", sent_at="2026-07-08 15:00 UTC",
    )
    assert digest["html"] != other["html"]
