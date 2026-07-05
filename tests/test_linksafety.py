from backend.linksafety import is_safe


def test_plain_domain_is_safe():
    ok, reason = is_safe("https://www.some-university.edu/jobs/abc")
    assert ok is True
    assert reason == "ok"


def test_shortener_is_withheld():
    ok, reason = is_safe("https://bit.ly/xyz")
    assert ok is False
    assert reason == "shortener"


def test_punycode_is_withheld():
    ok, reason = is_safe("https://xn--80ak6aa92e.com/apply")
    assert ok is False
    assert reason == "punycode"


def test_unparseable_is_withheld():
    ok, reason = is_safe("not a url")
    assert ok is False
    assert reason == "unparseable"


def test_allowlisted_host_is_safe():
    ok, reason = is_safe("https://jobs.lever.co/anthropic/123")
    assert ok is True
    assert reason == "allowlisted"


def test_allowlist_matches_subdomains():
    ok, reason = is_safe("https://apply.80000hours.org/x")
    assert ok is True
    assert reason == "allowlisted"


def test_young_domain_is_withheld():
    ok, reason = is_safe(
        "https://brand-new.example/apply",
        domain_age_days_fn=lambda host: 3,
        min_domain_age_days=30,
    )
    assert ok is False
    assert reason == "new-domain"


def test_old_domain_passes_age_check():
    ok, reason = is_safe(
        "https://established.example/apply",
        domain_age_days_fn=lambda host: 4000,
        min_domain_age_days=30,
    )
    assert ok is True
    assert reason == "ok"


def test_unknown_domain_age_fails_open():
    ok, reason = is_safe(
        "https://unknown.example/apply",
        domain_age_days_fn=lambda host: None,
        min_domain_age_days=30,
    )
    assert ok is True
    assert reason == "ok"
