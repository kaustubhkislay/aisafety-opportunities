"""Deadline enrichment.

Extraction often sees announcements that omit the deadline ("apply at <link>!").
When the message yields no deadline but has a safe link, we fetch that page,
reduce it to text, and ask the model for the application deadline — so Airtable
(and the site) get repopulated with a real date instead of "no deadline".

Fail-soft everywhere: an unreachable page, malformed answer, or spent LLM
budget simply leaves the deadline empty.
"""

import json
import logging
import re

log = logging.getLogger("enrich")

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"\s+")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEADLINE_PROMPT = (
    "You are given the text of an opportunity's application page. "
    'Return ONLY a JSON object {"deadline": "YYYY-MM-DD"} with the application '
    'deadline, or {"deadline": null} if the page states none. Use the latest '
    "deadline if several rounds are listed."
)


def page_text(url: str, get=None, max_bytes: int = 200_000) -> str | None:
    """Fetch a page and reduce it to visible text; None on any failure."""
    if get is None:
        import httpx

        get = httpx.get
    try:
        res = get(url, timeout=20, follow_redirects=True)
    except Exception:  # noqa: BLE001 - enrichment is best-effort
        log.warning("enrich: could not fetch %s", url)
        return None
    if not 200 <= res.status_code < 300:
        return None
    text = _TAG_RE.sub(" ", res.text[:max_bytes])
    return _WS_RE.sub(" ", text).strip()


class DeadlineFinder:
    """LLM call that extracts a deadline from page text."""

    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def find(self, text: str) -> str | None:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": DEADLINE_PROMPT},
                {"role": "user", "content": text[:20_000]},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        try:
            return json.loads(resp.choices[0].message.content).get("deadline")
        except (ValueError, TypeError, AttributeError):
            return None


def enrich_deadline(url: str, *, page_text_fn, find_fn, spend_guard=None) -> str | None:
    """Best-effort deadline for ``url``; validated ISO date or None."""
    text = page_text_fn(url)
    if not text:
        return None
    if spend_guard is not None and not spend_guard.try_acquire():
        log.info("enrich: spend cap hit; skipping deadline lookup for %s", url)
        return None
    try:
        deadline = find_fn(text)
    except Exception:  # noqa: BLE001 - never let enrichment break publishing
        log.exception("enrich: deadline lookup failed for %s", url)
        return None
    if isinstance(deadline, str) and _ISO_RE.match(deadline.strip()):
        return deadline.strip()
    return None
