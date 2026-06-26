from urllib.parse import urlparse

_SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "buff.ly",
    "is.gd",
    "rebrand.ly",
}

_DENYLIST: set[str] = set()  # populated over time as bad actors are found


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_safe(url: str) -> tuple[bool, str]:
    host = _host(url)
    if not host:
        return (False, "unparseable")
    if host in _DENYLIST:
        return (False, "denylisted")
    if host in _SHORTENERS:
        return (False, "shortener")
    if host.startswith("xn--") or ".xn--" in host:
        return (False, "punycode")
    return (True, "ok")
