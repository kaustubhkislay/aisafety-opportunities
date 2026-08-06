"""LLM-assisted duplicate detection across differing links.

URL-keyed dedup (``backend/dedup.py``) cannot merge the same opportunity
published under two different URLs — live case: one announcement cross-posted
to two communities, where extraction picked the info page once and the
application form the other time. This module screens published records with
cheap heuristics and asks the LLM whether a surviving candidate describes the
same opportunity. Fail-soft everywhere: any failure means "no match", i.e. at
worst the pre-existing duplicate-on-the-board behavior.
"""

import json
import logging
import re

log = logging.getLogger("semantic_dedup")

# A candidate must show at least two independent signals (deadline, title,
# org) before it is worth an LLM call — deadlines cluster too much alone.
_SIGNALS_REQUIRED = 2
_TITLE_JACCARD = 0.5
# Exception: a long near-identical title stands alone when a deadline is
# missing on either side — live case: a DCMC cross-post where one variant had
# no extractable deadline and the org was spelled differently ("DCMC" vs
# "DC Mini-Conference"), so neither backup signal could fire.
_STRONG_TITLE_TOKENS = 4

JUDGE_PROMPT = (
    "You judge whether two postings describe the same opportunity — the same "
    "program, role, grant, or event from the same organization — even when "
    "titles, links, or wording differ. Different cohorts or rounds of the "
    "same program are the same opportunity only if their deadlines match. "
    'Return ONLY a JSON object: {"same_opportunity": bool}.'
)

_COMPARE_FIELDS = ("title", "org", "type", "deadline", "link", "location", "description")


def _tokens(value) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _strong_title_fallback(new_fields: dict, fields: dict) -> bool:
    """Title evidence alone, admissible only when a deadline is absent on one
    side (present-but-different deadlines suggest another round/cohort)."""
    if new_fields.get("deadline") and fields.get("deadline"):
        return False
    title_a, title_b = _tokens(new_fields.get("title")), _tokens(fields.get("title"))
    union = title_a | title_b
    shared = title_a & title_b
    if len(shared) < _STRONG_TITLE_TOKENS:
        return False
    return bool(union) and len(shared) / len(union) >= _TITLE_JACCARD


def _signals(new_fields: dict, fields: dict) -> int:
    score = 0
    if new_fields.get("deadline") and new_fields.get("deadline") == fields.get("deadline"):
        score += 1
    title_a, title_b = _tokens(new_fields.get("title")), _tokens(fields.get("title"))
    union = title_a | title_b
    if union and len(title_a & title_b) / len(union) >= _TITLE_JACCARD:
        score += 1
    if _tokens(new_fields.get("org")) & _tokens(fields.get("org")):
        score += 1
    return score


def find_candidates(new_fields: dict, records: list[dict], limit: int = 3) -> list[dict]:
    """Heuristic prefilter over published records ({"id", "fields"} shaped).

    Returns at most ``limit`` records worth an LLM judgment, best first.
    Records sharing the new item's dedup_key (already handled by the exact
    path) and expired records are never candidates.
    """
    scored = []
    for record in records:
        fields = record["fields"]
        if fields.get("dedup_key") == new_fields.get("dedup_key"):
            continue
        if fields.get("status") == "expired":
            continue
        score = _signals(new_fields, fields)
        if score < _SIGNALS_REQUIRED and _strong_title_fallback(new_fields, fields):
            score = _SIGNALS_REQUIRED
        if score >= _SIGNALS_REQUIRED:
            scored.append((score, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [record for _, record in scored[:limit]]


def _summary(fields: dict) -> dict:
    return {k: fields.get(k) for k in _COMPARE_FIELDS if fields.get(k)}


class DuplicateJudge:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def _call(self, new_fields: dict, existing_fields: dict) -> str:
        user = json.dumps(
            {"posting_a": _summary(existing_fields), "posting_b": _summary(new_fields)}
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return resp.choices[0].message.content

    def judge(self, new_fields: dict, existing_fields: dict) -> bool:
        for _ in range(2):
            try:
                verdict = json.loads(self._call(new_fields, existing_fields))
                return bool(verdict["same_opportunity"])
            except (KeyError, TypeError, ValueError):
                continue
        # Same poison-pill reasoning as extraction: at temperature 0 a
        # malformed verdict repeats forever. A missed merge is the safe side.
        log.warning("persistently malformed judge output; treating as distinct")
        return False


def make_semantic_matcher(backend, judge, spend_guard=None, limit: int = 3):
    """Return a ``fields -> record | None`` fallback for AirtableStore.upsert."""

    def matcher(fields: dict):
        try:
            records = backend.all()
        except Exception:  # noqa: BLE001 - a dedup nicety must never block publishing
            log.exception("candidate scan failed; skipping semantic dedup")
            return None
        for record in find_candidates(fields, records, limit=limit):
            if spend_guard is not None and not spend_guard.try_acquire():
                log.warning("spend cap hit; skipping semantic dedup judgment")
                return None
            if judge.judge(fields, record["fields"]):
                return record
        return None

    return matcher
