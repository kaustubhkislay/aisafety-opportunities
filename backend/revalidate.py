"""Site cache revalidation.

The website is statically rendered (ISR, hourly). Rather than asking community
owners to maintain Airtable automations, the backend pings the site's
``/api/revalidate`` endpoint itself right after it changes the canonical store —
publish (worker), retraction/purge (API), and status flips (daily job). Pings are
fail-soft: a miss just means the hourly ISR pass picks the change up instead.
"""

import logging

log = logging.getLogger("revalidate")

# Worker outcomes that changed what the site shows.
_PUBLISHED = {"created", "updated"}


def make_revalidator(env, post=None):
    """Return a zero-arg callable that POSTs the site's revalidate endpoint,
    or ``None`` when ``SITE_URL`` / ``REVALIDATE_SECRET`` are not configured."""
    site = (env.get("SITE_URL") or "").rstrip("/")
    secret = env.get("REVALIDATE_SECRET")
    if not site or not secret:
        return None
    if post is None:
        import httpx

        post = httpx.post
    # Secret travels in a header: query strings leak into request logs.
    url = f"{site}/api/revalidate"
    headers = {"x-revalidate-secret": secret}

    def revalidate() -> bool:
        try:
            res = post(url, headers=headers, timeout=10)
        except Exception:  # noqa: BLE001 - never let a cache ping break the pipeline
            log.exception("revalidate ping failed")
            return False
        if 200 <= res.status_code < 300:
            return True
        log.warning("revalidate ping failed: HTTP %s", res.status_code)
        return False

    return revalidate


def maybe_revalidate(status: str, revalidator) -> None:
    """Ping after a worker outcome that changed published content; no-op otherwise."""
    if revalidator is not None and status in _PUBLISHED:
        revalidator()
