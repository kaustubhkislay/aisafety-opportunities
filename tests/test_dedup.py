from backend.models import Opportunity
from backend.dedup import stable_key


def _opp(**kw):
    base = {"is_opportunity": True}
    base.update(kw)
    return Opportunity(**base)


def test_same_url_different_case_and_tracking_dedupes():
    a = _opp(link="https://WWW.Org.org/Apply/?utm_source=x")
    b = _opp(link="https://org.org/Apply")
    assert stable_key(a) == stable_key(b)
    assert stable_key(a).startswith("url:")


def test_no_link_uses_meta_hash():
    a = _opp(org="Redwood", title="ML Fellow", deadline="2026-08-01")
    key = stable_key(a)
    assert key.startswith("meta:")
    # deterministic
    assert key == stable_key(_opp(org="Redwood", title="ML Fellow", deadline="2026-08-01"))


def test_different_title_different_meta_key():
    a = _opp(org="Redwood", title="ML Fellow")
    b = _opp(org="Redwood", title="SWE Intern")
    assert stable_key(a) != stable_key(b)
