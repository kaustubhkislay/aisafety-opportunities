"""Daily dedup sweep.

The inline dedupe runs only when a message arrives; pairs can still land on
the board as duplicates (both variants published before either existed, a
judge call failed soft, or the spend cap skipped the semantic check). This
job re-screens the published board once a day with the same heuristics and
LLM judge, and merges confirmed pairs with the same attribution rules as the
inline path: older ``date_seen`` survives, ``source_servers`` accumulates,
content is never overwritten. Fail-soft everywhere — a failed judgment or
merge leaves the board exactly as it was.
"""

import logging

from backend.airtable import _union_servers
from backend.semantic_dedup import find_candidates

log = logging.getLogger("dedup_sweep")


def _pick_survivor(a: dict, b: dict) -> tuple[dict, dict]:
    """Older ``date_seen`` wins; missing counts as newer; ties keep ``a``
    (the earlier-fetched record)."""
    key_a = a["fields"].get("date_seen") or "9999-12-31"
    key_b = b["fields"].get("date_seen") or "9999-12-31"
    return (a, b) if key_a <= key_b else (b, a)


def run_dedup_sweep(backend, judge, spend_guard=None, revalidator=None) -> dict[str, int]:
    """Screen all published pairs, judge survivors, merge confirmed duplicates.

    ``backend`` provides ``all()``/``update()``/``delete()`` (Airtable shape:
    ``{"id", "fields"}``). ``judge`` is a ``DuplicateJudge``. Over-cap, the
    remaining pairs simply wait for tomorrow's run.
    """
    counts = {"pairs_judged": 0, "merged": 0}
    try:
        records = backend.all()
    except Exception:  # noqa: BLE001 - nothing to sweep without a board
        log.exception("record fetch failed; aborting sweep")
        return counts
    merged_away: set[str] = set()
    for i, record in enumerate(records):
        if record["id"] in merged_away:
            continue
        # find_candidates screens its *candidates* for expiry, but never sees
        # the left-hand record — check it here.
        if record["fields"].get("status") == "expired":
            continue
        later = [r for r in records[i + 1:] if r["id"] not in merged_away]
        for candidate in find_candidates(record["fields"], later):
            if record["id"] in merged_away:
                break  # this record lost an earlier merge in this loop
            if spend_guard is not None and not spend_guard.try_acquire():
                log.warning("spend cap hit; deferring remaining pairs to tomorrow")
                _finish(counts, revalidator)
                return counts
            counts["pairs_judged"] += 1
            if not judge.judge(record["fields"], candidate["fields"]):
                continue
            survivor, loser = _pick_survivor(record, candidate)
            servers = _union_servers(
                survivor["fields"].get("source_servers"),
                loser["fields"].get("source_servers"),
            )
            try:
                backend.update(survivor["id"], {"source_servers": servers})
                backend.delete(loser["id"])
            except Exception:  # noqa: BLE001 - one failed merge must not stop the rest
                log.exception(
                    "merge failed (%s <- %s); continuing", survivor["id"], loser["id"]
                )
                continue
            # Keep later unions in this run accumulating on the survivor.
            survivor["fields"]["source_servers"] = servers
            merged_away.add(loser["id"])
            counts["merged"] += 1
            log.info(
                "merged %r (%s, %s, %s) into %r (%s, %s, %s)",
                loser["fields"].get("title"), loser["fields"].get("org"),
                loser["fields"].get("link"), loser["id"],
                survivor["fields"].get("title"), survivor["fields"].get("org"),
                survivor["fields"].get("link"), survivor["id"],
            )
    _finish(counts, revalidator)
    return counts


def _finish(counts: dict, revalidator) -> None:
    log.info("dedup sweep: %s", counts)
    if counts["merged"] and revalidator is not None:
        revalidator()
