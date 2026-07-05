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

# Known-good hosts (matched including subdomains) that skip the heuristics
# below — established orgs and the big application platforms.
_ALLOWLIST = {
    "80000hours.org",
    "airtable.com",
    "ashbyhq.com",
    "greenhouse.io",
    "lever.co",
    "workable.com",
}


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _allowlisted(host: str) -> bool:
    return any(host == entry or host.endswith("." + entry) for entry in _ALLOWLIST)


def is_safe(
    url: str,
    *,
    domain_age_days_fn=None,
    min_domain_age_days=None,
) -> tuple[bool, str]:
    """Return ``(safe, reason)`` for a candidate opportunity link.

    ``domain_age_days_fn(host)`` is an optional hook (e.g. a WHOIS/RDAP lookup)
    returning the domain's age in days, or ``None`` when unknown. When provided
    together with ``min_domain_age_days``, younger domains are withheld;
    unknown age fails open (the other checks still apply).
    """
    host = _host(url)
    if not host:
        return (False, "unparseable")
    if host in _DENYLIST:
        return (False, "denylisted")
    if host in _SHORTENERS:
        return (False, "shortener")
    if host.startswith("xn--") or ".xn--" in host:
        return (False, "punycode")
    if _allowlisted(host):
        return (True, "allowlisted")
    if domain_age_days_fn is not None and min_domain_age_days is not None:
        age = domain_age_days_fn(host)
        if age is not None and age < min_domain_age_days:
            return (False, "new-domain")
    return (True, "ok")
