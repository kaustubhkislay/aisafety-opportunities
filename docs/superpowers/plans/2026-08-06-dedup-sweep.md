# Daily Dedup Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily cron job that scans published Airtable records for duplicate pairs the inline dedupe missed, confirms them with the existing LLM judge, and auto-merges them.

**Architecture:** One new module, `backend/dedup_sweep.py`, in the mold of `backend/status_job.py`: a pure `run_dedup_sweep` with injected dependencies plus an env-wiring `main()`. It reuses `semantic_dedup.find_candidates` (heuristic prefilter), `semantic_dedup.DuplicateJudge` (LLM verdict), `airtable._union_servers` (attribution merge), and `spend.SpendGuard` (cost cap). One new crontab line at 10:00 UTC.

**Tech Stack:** Python 3.12, pytest (`uv run --group dev pytest`), pyairtable backend object, OpenAI-compatible client.

**Spec:** `docs/superpowers/specs/2026-08-06-dedup-sweep-design.md`. One deliberate deviation: the spec sketches a `today` parameter, but expired records are excluded via their `status` field (maintained by the 09:00 status job), so the sweep needs no date. Also, `run_dedup_sweep` takes an optional `revalidator` so the "revalidate only on merge" rule is testable; `main()` stays thin.

## Global Constraints

- Run all Python tests with `uv run --group dev pytest` from the repo root.
- Fail-soft everywhere: a judge failure means "not a duplicate"; a merge failure logs and continues; the sweep must never raise out of a per-pair error.
- No new env vars. Reuse `LLM_DAILY_CALL_CAP`, `OPENAI_*`, `AIRTABLE_*`, `SITE_URL`/`REVALIDATE_SECRET`.
- No changes to `backend/semantic_dedup.py`, `backend/airtable.py`, or the inline pipeline.
- Commit messages follow repo style: short imperative subject, no prefix convention beyond plain English.

---

### Task 1: `run_dedup_sweep` core

**Files:**
- Create: `backend/dedup_sweep.py`
- Test: `tests/test_dedup_sweep.py`

**Interfaces:**
- Consumes: `semantic_dedup.find_candidates(new_fields, records, limit=3) -> list[record]`; `judge.judge(a_fields, b_fields) -> bool`; `airtable._union_servers(existing, incoming) -> str`; backend protocol `all() -> list[{"id","fields"}]`, `update(record_id, fields) -> None`, `delete(record_id) -> None`; `spend_guard.try_acquire() -> bool`.
- Produces: `run_dedup_sweep(backend, judge, spend_guard=None, revalidator=None) -> dict[str, int]` with keys `"pairs_judged"` and `"merged"`. Task 2's `main()` calls exactly this.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the daily dedup sweep (spec: 2026-08-06-dedup-sweep-design.md)."""

import pytest

from backend.dedup_sweep import run_dedup_sweep


def rec(id, title, org, deadline="2026-09-01", date_seen="2026-08-01",
        servers="Alpha", status="active", dedup_key=None):
    return {
        "id": id,
        "fields": {
            "title": title,
            "org": org,
            "deadline": deadline,
            "date_seen": date_seen,
            "source_servers": servers,
            "status": status,
            "dedup_key": dedup_key or f"url:{id}",
        },
    }


class FakeBackend:
    def __init__(self, records):
        self.records = records
        self.updates = []
        self.deletes = []
        self.fail_delete_ids = set()

    def all(self):
        return self.records

    def update(self, record_id, fields):
        self.updates.append((record_id, fields))

    def delete(self, record_id):
        if record_id in self.fail_delete_ids:
            raise RuntimeError("airtable down")
        self.deletes.append(record_id)


class FakeJudge:
    """Returns a canned verdict per unordered title pair; records calls."""

    def __init__(self, same=()):
        self.same = {frozenset(pair) for pair in same}
        self.calls = []

    def judge(self, a, b):
        self.calls.append((a["title"], b["title"]))
        return frozenset((a["title"], b["title"])) in self.same


class FakeGuard:
    def __init__(self, budget):
        self.budget = budget

    def try_acquire(self):
        if self.budget <= 0:
            return False
        self.budget -= 1
        return True


# The prefilter needs 2 of 3 signals; same deadline + same org qualifies
# even with disjoint titles.
PAIR = [
    rec("a", "ML Safety Fellowship", "Redwood", date_seen="2026-07-01"),
    rec("b", "Fellowship in ML Safety", "Redwood", date_seen="2026-07-20",
        servers="Beta"),
]


def test_no_candidates_no_calls_no_writes():
    backend = FakeBackend([
        rec("a", "ML Safety Fellowship", "Redwood", deadline="2026-09-01"),
        rec("b", "Biosecurity Grant", "OpenPhil", deadline="2026-10-15"),
    ])
    judge = FakeJudge()
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 0, "merged": 0}
    assert judge.calls == [] and backend.updates == [] and backend.deletes == []


def test_confirmed_pair_merges_into_older_record():
    backend = FakeBackend(list(PAIR))
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 1, "merged": 1}
    assert backend.updates == [("a", {"source_servers": "Alpha, Beta"})]
    assert backend.deletes == ["b"]


def test_missing_date_seen_counts_as_newer():
    a, b = rec("a", "ML Safety Fellowship", "Redwood", date_seen="2026-07-01"), \
        rec("b", "Fellowship in ML Safety", "Redwood", servers="Beta")
    del b["fields"]["date_seen"]
    backend = FakeBackend([b, a])  # newer record fetched first
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    run_dedup_sweep(backend, judge)
    assert backend.deletes == ["b"]
    assert backend.updates[0][0] == "a"


def test_judge_says_distinct_no_writes():
    backend = FakeBackend(list(PAIR))
    judge = FakeJudge()
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 1, "merged": 0}
    assert backend.updates == [] and backend.deletes == []


def test_spend_cap_exhausted_skips_remaining_pairs():
    records = list(PAIR) + [
        rec("c", "Governance Course", "BlueDot", deadline="2026-11-01"),
        rec("d", "Course on Governance", "BlueDot", deadline="2026-11-01",
            servers="Gamma"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    counts = run_dedup_sweep(backend, judge, spend_guard=FakeGuard(1))
    assert counts == {"pairs_judged": 1, "merged": 1}
    assert len(judge.calls) == 1  # second pair waits for tomorrow


def test_merged_loser_not_compared_again():
    records = list(PAIR) + [
        rec("c", "ML Safety Fellowship 2026", "Redwood", date_seen="2026-07-25",
            servers="Gamma"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[
        ("ML Safety Fellowship", "Fellowship in ML Safety"),
        ("ML Safety Fellowship", "ML Safety Fellowship 2026"),
    ])
    counts = run_dedup_sweep(backend, judge)
    assert counts["merged"] == 2
    assert backend.deletes == ["b", "c"]
    # b was merged away; it must never appear in a later judgment
    assert all("Fellowship in ML Safety" not in call or "ML Safety Fellowship" in call
               for call in judge.calls)
    losers_judged = [c for c in judge.calls if set(c) ==
                     {"Fellowship in ML Safety", "ML Safety Fellowship 2026"}]
    assert losers_judged == []


def test_survivor_accumulates_servers_across_merges():
    records = list(PAIR) + [
        rec("c", "ML Safety Fellowship 2026", "Redwood", date_seen="2026-07-25",
            servers="Gamma"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[
        ("ML Safety Fellowship", "Fellowship in ML Safety"),
        ("ML Safety Fellowship", "ML Safety Fellowship 2026"),
    ])
    run_dedup_sweep(backend, judge)
    assert backend.updates[-1] == ("a", {"source_servers": "Alpha, Beta, Gamma"})


def test_expired_record_never_screened():
    records = [
        rec("a", "ML Safety Fellowship", "Redwood", status="expired"),
        rec("b", "Fellowship in ML Safety", "Redwood", servers="Beta"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 0, "merged": 0}


def test_delete_failure_logs_and_continues():
    records = list(PAIR) + [
        rec("c", "Governance Course", "BlueDot", deadline="2026-11-01"),
        rec("d", "Course on Governance", "BlueDot", deadline="2026-11-01",
            servers="Gamma", date_seen="2026-08-02"),
    ]
    backend = FakeBackend(records)
    backend.fail_delete_ids = {"b"}
    judge = FakeJudge(same=[
        ("ML Safety Fellowship", "Fellowship in ML Safety"),
        ("Governance Course", "Course on Governance"),
    ])
    counts = run_dedup_sweep(backend, judge)
    assert counts["merged"] == 1  # first merge failed, second landed
    assert backend.deletes == ["d"]


def test_revalidator_fires_only_on_merge():
    pings = []
    backend = FakeBackend(list(PAIR))
    run_dedup_sweep(backend, FakeJudge(), revalidator=lambda: pings.append(1))
    assert pings == []
    backend = FakeBackend(list(PAIR))
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    run_dedup_sweep(backend, judge, revalidator=lambda: pings.append(1))
    assert pings == [1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_dedup_sweep.py -v`
Expected: FAIL at import — `ModuleNotFoundError: No module named 'backend.dedup_sweep'`

- [ ] **Step 3: Write the implementation**

```python
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
```

Implementation notes for the engineer:
- `find_candidates` (in `backend/semantic_dedup.py`) already excludes expired **candidates** and same-`dedup_key` records; the explicit `status == "expired"` check covers the **left-hand** record, which `find_candidates` never sees.
- The `break` on `record["id"] in merged_away` handles the case where the *earlier* record was the loser (its candidate had an older `date_seen`): the record is gone, so its remaining candidates must not be judged against it.
- Mutating `survivor["fields"]["source_servers"]` in place keeps later unions in the same run accumulating (tested by `test_survivor_accumulates_servers_across_merges`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_dedup_sweep.py -v`
Expected: all 10 PASS

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `uv run --group dev pytest`
Expected: all pass (288 previously collected + 10 new)

- [ ] **Step 6: Commit**

```bash
git add backend/dedup_sweep.py tests/test_dedup_sweep.py
git commit -m "Add daily dedup sweep core"
```

---

### Task 2: `main()` wiring, crontab, docs

**Files:**
- Modify: `backend/dedup_sweep.py` (append `main()`)
- Modify: `deploy/crontab`
- Modify: `ARCHITECTURE.md` (cron process row)

**Interfaces:**
- Consumes: `run_dedup_sweep(backend, judge, spend_guard=None, revalidator=None)` from Task 1; `backend.airtable.backend_from_env()`; `backend.semantic_dedup.DuplicateJudge(client, model)`; `backend.spend.SpendGuard.from_env(env)`; `backend.revalidate.make_revalidator(env)`.
- Produces: `python -m backend.dedup_sweep` as a cron entrypoint.

- [ ] **Step 1: Append `main()` to `backend/dedup_sweep.py`**

Mirror `backend/status_job.py:main` (env wiring is not unit-tested in this repo; CI's Docker import gate covers it):

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    import os

    from openai import OpenAI

    from backend.airtable import backend_from_env
    from backend.revalidate import make_revalidator
    from backend.semantic_dedup import DuplicateJudge
    from backend.spend import SpendGuard

    client = OpenAI(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    judge = DuplicateJudge(client, os.environ["OPENAI_MODEL"])
    spend_guard = SpendGuard.from_env(os.environ)
    if spend_guard is None:
        log.warning("LLM_DAILY_CALL_CAP unset — sweep spend is uncapped")
    run_dedup_sweep(
        backend_from_env(), judge,
        spend_guard=spend_guard, revalidator=make_revalidator(os.environ),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add the crontab line**

In `deploy/crontab`, extend the comment and add the 10:00 line between status and digest so the file reads:

```
# Times in UTC. status: daily; dedup sweep: daily (after status, before digest); digest: daily (previous day's new items; skips empty days).
0 9 * * * cd /app && python -m backend.status_job
0 10 * * * cd /app && python -m backend.dedup_sweep
0 15 * * * cd /app && python -m backend.digest
```

- [ ] **Step 3: Update ARCHITECTURE.md**

Find the cron row in the process table (it names `backend.status_job` 09:00 and `backend.digest` 15:00) and add `backend.dedup_sweep` 10:00 UTC with a half-line description: "re-screens the published board for duplicate pairs the inline dedupe missed and auto-merges them". Match the table's existing phrasing style.

- [ ] **Step 4: Verify the module runs as an entrypoint without env**

Run: `uv run python -c "import backend.dedup_sweep"`
Expected: no output, exit 0 (imports at module top must not require env vars).

- [ ] **Step 5: Run the full suite**

Run: `uv run --group dev pytest`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/dedup_sweep.py deploy/crontab ARCHITECTURE.md
git commit -m "Wire dedup sweep into cron"
```

---

## Deployment note (post-merge, not a plan task)

`fly-deploy.yml` path-filters on `backend/**` and `deploy/**`, so merging to `main` redeploys the machine and the new crontab automatically. Watch the first 10:00 UTC run in `fly logs` for the `dedup sweep: {...}` summary line.
