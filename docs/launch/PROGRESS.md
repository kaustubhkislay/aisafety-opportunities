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
| T2.1 | Slice 4: daily status/expiry job + tests | auto | done | backend/status_job.py; 9 tests; suite 52 green; merged via PR #6 |
| T3.1 | Slice 5: edge exclusion (tags + private-default) | auto | done | bot/exclusion.py; guards live + backfill; 13 tests; suite 65; merged via PR #7 |
| T3.2 | Slice 5: per-channel public/private config | auto | done | bot/channel_config.py; wired into client; 8 tests; suite 73; merged via PR #8 |
| T3.3 | Slice 5: retraction (lock-emoji / [private] edit) | auto | done | bot/retraction.py + /retract + delete_by_message; worker stamps source_message_id; 11 tests; suite 84; merged via PR #9 |
| T3.4 | Slice 5: uninstall purge + owner-visibility view | auto | done | backend/purge.py + /purge + /ingested; on_guild_remove; 8 tests; suite 92; merged via PR #10 |
| T3.5 | Slice 5: Discord OAuth app + install flow | ckpt | pending | external app registration |
| T4.1 | Slice 6: subscribe form + store + digest + unsub | auto | done | backend subscribers+digest (HMAC unsub) + /subscribe,/unsubscribe; web form+proxy; 23 tests; suite 111; merged via PR #11 |
| T4.2 | Slice 6: email sender account + API key | ckpt | pending | Resend/Buttondown |
| T5.1 | Slice 7: privacy + terms pages, footer wiring | auto | done | web/app/{privacy,terms}/page.tsx; footer + metadata + web README fixed; 9 tests; web 40, backend 111 green |
| T6.1 | Airtable base schema + revalidate automation | ckpt | pending | |
| T6.2 | Backend host (Railway/Fly) + env + cron | ckpt | pending | |
| T6.3 | Vercel deploy + env vars | ckpt | pending | |
| T6.4 | LLM spend cap (config + enforcement) | auto | done | backend/spend.py SpendGuard (LLM_DAILY_CALL_CAP, per-UTC-day) wired into worker; env docs reconciled to OPENAI_*; 7 tests; backend 118 green |
| T6.5 | End-to-end smoke on a controlled server | ckpt | pending | the demo is the pitch |

## Folded-in fixes (attach to the noted milestone)
- deadline ISO validation → T2.1 / extraction
- ~~link-safety brand-new-domain + allowlist heuristics → T3.x / pipeline hardening~~ **resolved in Phase 1 hardening**
- ~~cheap filter requires a URL (drops email-only opps) → revisit at T3.1 / filter~~ **resolved in Phase 1 hardening**
- T3/T5/T7 SDD test-coverage minors → opportunistic in the relevant slice
- ~~`.env.example` lists `ANTHROPIC_API_KEY` but `backend/worker.py` reads `OPENAI_BASE_URL`/`OPENAI_API_KEY`/`OPENAI_MODEL` (OpenAI-compatible client) → reconcile env docs at T6.4 / deploy~~ **resolved in T6.4**
- Airtable schema now needs a `source_message_id` field (worker writes it; retraction finds by it) → add to the base schema at T6.1
- retraction of an item deduped across multiple source messages only matches its latest `source_message_id` (v1 limitation; documented in `delete_by_message`)

## Log
- 2026-07-05 — Phase 1 hardening batch (TDD): filter accepts email-only opportunities (URL *or* email + keyword); linksafety gains allowlist (subdomain-aware, big application platforms) + injectable domain-age hook (`domain_age_days_fn`/`min_domain_age_days`, young → withheld "new-domain", unknown age fails open); missing channels.json now logs a WARNING (fail-open is loud); web: `loadOpportunitiesResult` exposes a `degraded` flag and the home page shows an unavailability notice instead of a silent empty list; feed.xml uses an obvious `.invalid` placeholder + console.error when SITE_URL unset (no more example.com); RSS items get `pubDate` from date_seen and escape single quotes; new coverage for /api/subscribe and /feed.xml routes; scaffold.test.ts deleted. Backend 127 + web 51 green; lint clean. **Phase 1 (all [auto] code work) complete — remaining tasks are [ckpt] provisioning + T6.5 smoke.**
- 2026-06-26 — ledger created; all tasks pending.
- 2026-06-26 — T0.1 done: `.github/workflows/ci.yml` (backend pytest + web vitest/build, per-job guards). Merged via PR #4.
- 2026-06-26 — M1 complete: PRs #1/#3/#4 merged by owner. CI caught two issues: PR #2 (extraction) was orphaned (stacked-PR merge dropped it) and the site build crashed with no Airtable env. Both fixed in PR #5 (recover extraction + `loadOpportunities` build fallback); 43 backend + 27 web tests green. Merged.
- 2026-06-26 — T2.1 done: `backend/status_job.py` — `derive_status` (mirrors web `deriveStatus`) + `run_status_job` (updates only changed records). Added `PyairtableBackend.all()`. 9 tests; full suite 52 green. Merged via PR #6.
- 2026-06-26 — T3.1 done: `bot/exclusion.py` `should_exclude` (tag vocabulary, word-boundary match, private-default channels). Wired into BOTH transmit paths — `Ingestor._forward` (live) and `backfill_channel` — so excluded messages never transmit (and are logged). 13 tests; suite 65. Merged via PR #7.
- 2026-06-26 — T3.2 done: `bot/channel_config.py` `ChannelConfig` (per-channel public/private + fail-closed fallback, JSON-loaded); wired into client as the real `channel_default_fn`. 8 tests; suite 73. Merged via PR #8.
- 2026-06-26 — T3.3 done: retraction. `bot/retraction.py` detectors + `Forwarder.retract`; secured `/retract` deletes the Airtable record (`delete_by_message`) and tombstones the raw row; worker stamps `source_message_id`. 11 tests; suite 84. Merged via PR #9.
- 2026-06-26 — T3.4 done: uninstall purge + owner view. `backend/purge.py` `purge_server` clears both stores; `AirtableStore.delete_by_server` + `RawStore.{get_messages_by_server,delete_server}`; secured `/purge` + `/ingested/{server_id}`; `Forwarder.purge` wired to `on_guild_remove`. 8 tests; full suite 92 green. Merged via PR #10. **M3 autonomous work complete.**
- 2026-07-05 — T6.4 done: LLM spend cap. `backend/spend.py` `SpendGuard` — per-UTC-day call counter from `LLM_DAILY_CALL_CAP` (unset/0 = uncapped, worker warns); `try_acquire` resets on period change; charged in `process_message` after the cheap filter and before the LLM call, so filtered rows cost nothing; over cap raises `SpendCapExceeded` → row left unprocessed, retries next period. Env docs reconciled: `.env.example` now documents `OPENAI_BASE_URL`/`OPENAI_API_KEY`/`OPENAI_MODEL` (folded-in fix resolved). 7 tests (TDD); backend 118 green. Phase 1 remaining: hardening batch.
- 2026-07-05 — T5.1 done: legal pages. `web/app/privacy/page.tsx` (edge-exclusion tag vocabulary, curated-fields-only/no raw text, retraction/purge/owner visibility, subscriber-email + unsubscribe, takedown contact) + `web/app/terms/page.tsx` (as-is, acceptable use). Footer now links Privacy · Terms (dead `/privacy` link fixed); layout metadata replaced ("Create Next App" → real title/description); `web/README.md` rewritten from create-next-app boilerplate. 9 new tests (TDD); web 40 + backend 111 green; lint clean; `/privacy` + `/terms` prerender static. Next: T6.4 spend cap + env reconcile.
- 2026-07-05 — Phase 0 cleanup: PR #11 merged (T4.1 complete on main); stale "PR pending" notes updated to their merged PR numbers; `*.db` gitignored (local `subscribers.db`/`raw.db` never commit). Next: T5.1 legal pages.
- 2026-06-27 — T4.1 done: email digest. `backend/subscribers.py` (SQLite, idempotent add/remove/reactivate) + `backend/digest.py` (email validation, HMAC unsubscribe tokens, `build_digest`, `run_digest` filtering expired + `since`, runnable `main()` with placeholder sender). Public `POST /subscribe` + token `GET /unsubscribe`. Web: `lib/subscribe.ts` + `/api/subscribe` proxy (backend URL stays server-side) + `SubscribeForm` on the page. 23 tests (backend 19 + web 4); backend suite 111, web 31 green. Real email sender deferred to T4.2 (ckpt). Next: T5.1 legal pages.
