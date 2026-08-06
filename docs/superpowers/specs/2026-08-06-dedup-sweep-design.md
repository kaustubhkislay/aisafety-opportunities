# Daily dedup sweep

**Date:** 2026-08-06
**Status:** Approved design

## Problem

The inline dedupe runs only when a new message arrives: an exact `dedup_key`
match first, then the semantic LLM judge against published records. Pairs can
still land on the board as duplicates — e.g. both variants arrive before either
is published, a judge call fails soft, or the spend cap skips the semantic
check. Nothing ever re-examines the published board, so such pairs persist
until a human notices.

## Goal

A daily job that scans the published Airtable records for duplicate pairs the
inline path missed, confirms each candidate pair with the existing LLM judge,
and auto-merges confirmed pairs using the same attribution rules as the inline
path. No human step.

## Approach

A standalone cron module, `backend/dedup_sweep.py`, in the mold of
`backend/status_job.py`: a pure `run_dedup_sweep` function with injected
dependencies plus a `main()` that wires production objects from env.
It reuses `semantic_dedup.find_candidates` and `semantic_dedup.DuplicateJudge`
unchanged.

Alternatives rejected: folding the sweep into `status_job` (tangles two jobs
and their failure modes) and embedding-based clustering (new dependency and
infrastructure for a board of a few hundred records).

## Design

### `run_dedup_sweep(backend, judge, spend_guard, today) -> dict[str, int]`

1. Fetch all records once via `backend.all()`.
2. For each record, screen only the records **after** it in the list with
   `find_candidates`, so each unordered pair is screened once. The existing
   prefilter semantics apply: same-`dedup_key` and expired records are never
   candidates, and a pair needs 2 of 3 signals (deadline equality,
   title Jaccard >= 0.5, org overlap).
3. For each surviving pair: `spend_guard.try_acquire()` gates the LLM call;
   over cap, skip the remaining pairs (they retry next night). Then
   `judge.judge(a_fields, b_fields)`. All existing fail-soft and poison-pill
   behavior carries over — any failure means "not a duplicate".
4. On a confirmed pair, merge with the inline attribution rules:
   - The record with the **older `date_seen`** survives (a missing
     `date_seen` counts as newer; ties: the first fetched). "Newly added" on the site never resurfaces a repost.
   - The survivor's `source_servers` becomes the comma-joined union of both.
   - The survivor's content is **not** overwritten (same reasoning as the
     inline semantic path: overwriting flips link/title between variants).
   - The loser is deleted from Airtable.
5. A merged loser takes no further part in the run (skip set).
6. Return counts: `{"pairs_judged", "merged"}` (log them like the status job).

### `main()`

Mirrors `status_job.main()`: `backend_from_env()`, an OpenAI-compatible client
and `DuplicateJudge` built the same way `worker.py` builds them, a `SpendGuard`
from the same daily-cap env var the worker uses, `date.today()`. After the
sweep, ping the revalidator (`make_revalidator`) only when `merged > 0`.

### Scheduling

One new line in `deploy/crontab`:

```
0 10 * * * cd /app && python -m backend.dedup_sweep
```

10:00 UTC sits after the status job (09:00 — expiries land first, so expired
records are excluded from screening) and before the digest (15:00 — the digest
never mails a freshly-mergeable duplicate).

### Audit trail

Each merge logs, at INFO: both titles, orgs, links, both record ids, and which
survived. Fly logs are the audit trail; no new storage.

### Error handling

- Per-pair: any judge exception or malformed verdict → not a duplicate
  (existing `DuplicateJudge` behavior).
- Per-run: an Airtable fetch failure aborts the run with a logged exception —
  cron retries tomorrow. A delete/update failure on one merge logs and
  continues with the next pair.
- Spend cap shared with the worker: the sweep can consume cap headroom, but it
  runs once daily against a small candidate set (heuristic prefilter first),
  so the cost is a handful of calls. The sweep is a repair job; starving it is
  always safe.

## Out of scope

- No changes to the inline pipeline or to `semantic_dedup.py`.
- No new env vars.
- No persistence of past verdicts: re-judging the same surviving pair nightly
  is a few temperature-0 calls and keeps the job stateless. If the board grows
  enough that this matters, add a judged-pairs table then.

## Testing

`tests/test_dedup_sweep.py`, fakes only (repo pattern):

- No candidate pairs → zero judge calls, zero writes.
- Confirmed pair → older `date_seen` survives, `source_servers` unioned,
  loser deleted, counts correct.
- Judge says "distinct" → no writes.
- Spend cap exhausted mid-run → remaining pairs skipped, no exception.
- A merged loser is not screened or judged again in the same run.
- Revalidator fires only when at least one merge happened.
- A delete failure on one pair does not stop later pairs.
