# Launch progress ledger

The `/loop` runner reads and writes this file. One task per pass, top to bottom.
Status: `pending` · `in-progress` · `done` · `blocked-ckpt`.
Tags: `[auto]` (loop does it) · `[ckpt]` (needs the human; loop stops).

Design: `docs/launch/2026-06-26-launch-plan-design.md`
Plan:   `docs/launch/2026-06-26-launch-plan.md`

## How a pass works
1. Read this file. Pick the first task whose status is `pending`.
2. `[auto]` → implement via TDD, run the full suite, commit, set status `done`, add a one-line note (commit SHA).
3. `[ckpt]` → set status `blocked-ckpt`, stop, and tell the human exactly what to do. Do not proceed past it.
4. After an `[auto]` task, offer a review checkpoint before the next pass.

## Tasks

| # | Task | Tag | Status | Note |
|---|------|-----|--------|------|
| T0.1 | CI: pytest (backend+bot) + vitest (web) on PRs | auto | done | ci.yml; merged in PR #4 |
| T0.2 | Branch sequencing: merge #1 → rebase #2 → #3 | auto | done | superseded — all PRs merged directly |
| T1.1 | Review + merge PR #1 (bot ingestion) | ckpt | done | merged |
| T1.2 | Review + merge PR #2 (extraction pipeline) | ckpt | done | PR #2 orphaned; recovered+merged via PR #5 |
| T1.3 | Review + merge PR #3 (public website) | ckpt | done | merged |
| T0.3 | Fix: env-resilient site build (loadOpportunities) | auto | done | unplanned; CI fallout; PR #5 |
| T2.1 | Slice 4: daily status/expiry job + tests | auto | done | backend/status_job.py; 9 tests; suite 52 green; PR pending |
| T3.1 | Slice 5: edge exclusion (tags + private-default) | auto | pending | drop before transmit |
| T3.2 | Slice 5: per-channel public/private config | auto | pending | |
| T3.3 | Slice 5: retraction (lock-emoji / [private] edit) | auto | pending | |
| T3.4 | Slice 5: uninstall purge + owner-visibility view | auto | pending | |
| T3.5 | Slice 5: Discord OAuth app + install flow | ckpt | pending | external app registration |
| T4.1 | Slice 6: subscribe form + store + digest + unsub | auto | pending | |
| T4.2 | Slice 6: email sender account + API key | ckpt | pending | Resend/Buttondown |
| T5.1 | Slice 7: privacy + terms pages, footer wiring | auto | pending | |
| T6.1 | Airtable base schema + revalidate automation | ckpt | pending | |
| T6.2 | Backend host (Railway/Fly) + env + cron | ckpt | pending | |
| T6.3 | Vercel deploy + env vars | ckpt | pending | |
| T6.4 | LLM spend cap (config + enforcement) | auto | pending | |
| T6.5 | End-to-end smoke on a controlled server | ckpt | pending | the demo is the pitch |

## Folded-in fixes (attach to the noted milestone)
- deadline ISO validation → T2.1 / extraction
- link-safety brand-new-domain + allowlist heuristics → T3.x / pipeline hardening
- cheap filter requires a URL (drops email-only opps) → revisit at T3.1 / filter
- T3/T5/T7 SDD test-coverage minors → opportunistic in the relevant slice

## Log
- 2026-06-26 — ledger created; all tasks pending.
- 2026-06-26 — T0.1 done: `.github/workflows/ci.yml` (backend pytest + web vitest/build, per-job guards). Merged via PR #4.
- 2026-06-26 — M1 complete: PRs #1/#3/#4 merged by owner. CI caught two issues: PR #2 (extraction) was orphaned (stacked-PR merge dropped it) and the site build crashed with no Airtable env. Both fixed in PR #5 (recover extraction + `loadOpportunities` build fallback); 43 backend + 27 web tests green. Merged.
- 2026-06-26 — T2.1 done: `backend/status_job.py` — `derive_status` (mirrors web `deriveStatus`) + `run_status_job` (updates only changed records). Added `PyairtableBackend.all()`. 9 tests; full suite 52 green. Folds in the deadline-ISO-validation deferred item (malformed → active + warn). Next: M3 / T3.1 edge exclusion.
