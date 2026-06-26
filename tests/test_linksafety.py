from backend.linksafety import is_safe


def test_plain_domain_is_safe():
    ok, reason = is_safe("https://www.80000hours.org/jobs/abc")
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
