import logging

from backend.revalidate import make_revalidator, maybe_revalidate


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_returns_none_without_env():
    assert make_revalidator({}) is None
    assert make_revalidator({"SITE_URL": "https://s.example"}) is None
    assert make_revalidator({"REVALIDATE_SECRET": "x"}) is None


def test_posts_revalidate_url():
    calls = []

    def post(url, timeout):
        calls.append(url)
        return FakeResponse(200)

    ping = make_revalidator(
        {"SITE_URL": "https://aisopportunities.com/", "REVALIDATE_SECRET": "sec"},
        post=post,
    )
    assert ping() is True
    assert calls == ["https://aisopportunities.com/api/revalidate?secret=sec"]


def test_fail_soft_on_http_error(caplog):
    ping = make_revalidator(
        {"SITE_URL": "https://s.example", "REVALIDATE_SECRET": "sec"},
        post=lambda url, timeout: FakeResponse(401),
    )
    with caplog.at_level(logging.WARNING, logger="revalidate"):
        assert ping() is False
    assert any("401" in r.message for r in caplog.records)


def test_fail_soft_on_exception():
    def post(url, timeout):
        raise OSError("network down")

    ping = make_revalidator(
        {"SITE_URL": "https://s.example", "REVALIDATE_SECRET": "sec"},
        post=post,
    )
    assert ping() is False  # never raises — hourly ISR is the fallback


def test_maybe_revalidate_pings_only_on_published_changes():
    pings = []
    reval = lambda: pings.append(1) or True  # noqa: E731

    for status in ("created", "updated"):
        maybe_revalidate(status, reval)
    for status in ("skipped_filter", "not_opportunity", "withheld"):
        maybe_revalidate(status, reval)
    assert len(pings) == 2


def test_maybe_revalidate_tolerates_none():
    maybe_revalidate("created", None)  # no revalidator configured — no-op
