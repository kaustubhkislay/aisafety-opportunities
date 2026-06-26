import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse

_TRACKING = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    query_items = sorted(
        (k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKING
    )
    base = host + path
    if query_items:
        base += "?" + urlencode(query_items)
    return base


def stable_key(opp) -> str:
    if opp.link:
        return "url:" + normalize_url(opp.link)
    basis = f"{(opp.org or '').lower()}|{(opp.title or '').lower()}|{opp.deadline or ''}"
    return "meta:" + hashlib.sha256(basis.encode()).hexdigest()[:16]
