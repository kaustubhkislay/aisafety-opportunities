# Launch plan — aisafety-opportunities — design

Status: approved 2026-06-26. Target end state: **launch-ready (through Slice 8)**.
Runner: a written implementation plan driven by a **checkpointed `/loop`** (one task per pass, human-in-the-loop).

This document is the *map* to launch. The per-task execution detail lives in the
implementation plan (`docs/launch/2026-06-26-launch-plan.md`); live status lives in
`docs/launch/PROGRESS.md`, which the loop reads and writes each pass.

## Starting state (2026-06-26)

Three open, mergeable PRs, no CI, no GitHub reviews:

- **PR #1** `feat/discord-ingestion-slice` — Slice 1: Discord bot → ingest API → raw SQLite store + downtime backfill.
- **PR #2** `feat/extraction-pipeline` — Slice 2: cheap filter → LLM extract → link-safety → dedup-upsert → Airtable. Built **on top of #1** (contains all `bot/` files). SDD ledger: 43 tests, "READY TO MERGE".
- **PR #3** `feat/public-website` — Slice 3: Next.js ISR site reading Airtable + RSS + secured revalidate webhook. Branches **independently off `main`**.

Known gaps carried forward (from the Slice-2 SDD ledger and design review):
deadline ISO validation; link-safety brand-new-domain/allowlist heuristics; cheap
filter requires a URL (drops email-only opportunities); no LLM spend cap; the
T3/T5/T7 test-coverage minors. Each is folded into the relevant milestone below.

## Auto vs checkpoint

Every task is tagged:

- `[auto]` — a `/loop` pass can complete it: write code via TDD, run the suite, commit, update the ledger.
- `[ckpt]` — needs the human: credentials, an external account/registration, a deploy, or a PR review. The loop **stops** and surfaces exactly what is needed, then waits.

## Milestones

### M0 — Foundation (before merging)
- `[auto]` **T0.1 CI** — GitHub Actions: `pytest` for `backend/`+`bot/`, `vitest` for `web/`, on every PR. (No checks exist today; the "auditable, open-source" positioning wants green CI.)
- `[auto]` **T0.2 Branch sequencing** — #2 contains #1; #3 is independent. Order: merge #1 → rebase #2 on main → #3 merges clean.

### M1 — Merge slices 1–3
- `[ckpt]` **T1.1 / T1.2 / T1.3** — review + merge PR #1 (bot), #2 (extraction), #3 (site). Human review gate per PR.

### M2 — Slice 4: daily status/expiry job
- `[auto]` **T2.1** — scheduled re-evaluation of Airtable `deadline` → `status` (`active`/`closing-soon`/`expired`); tests. The site already derives status live, so this serves the canonical store and the digest, not the site.

### M3 — Slice 5: installable bot + edge privacy (the trust core)
- `[auto]` **T3.1 edge exclusion** — drop, and never transmit, messages matching the tag vocabulary (`[private]`, `school-specific`, `internal`, `do-not-share`) or posted in a private-default channel. Runs in the bot, before transmit.
- `[auto]` **T3.2 channel config** — per-channel public-default vs private-default, captured at install.
- `[auto]` **T3.3 retraction** — lock-emoji reaction / `[private]` edit → delete the record from the site. Doubles as general takedown.
- `[auto]` **T3.4 uninstall purge + owner view** — removing the bot purges that server's data; owner can see what was ingested.
- `[ckpt]` **T3.5 OAuth install** — register the Discord OAuth app and wire the install/authorize flow (external app registration).

### M4 — Slice 6: email digest
- `[auto]` **T4.1** — subscribe form on the site + subscriber store + scheduled digest job + unsubscribe link.
- `[ckpt]` **T4.2** — sender account (Resend or Buttondown) + API key in env.

### M5 — Slice 7: legal pages
- `[auto]` **T5.1** — plain-English privacy policy + terms; footer wiring (replaces the placeholder slot). Reflects the edge-exclusion, retraction, purge, and subscriber-email facts as actually built.

### M6 — Deploy / launch infra (mostly checkpoints)
- `[ckpt]` **T6.1 Airtable** — base schema + automation → `/api/revalidate` webhook.
- `[ckpt]` **T6.2 backend host** — Railway/Fly always-on container + env + cron for the status & digest jobs.
- `[ckpt]` **T6.3 Vercel** — deploy `web/` + env vars.
- `[auto]` **T6.4 LLM spend cap** — config + enforcement around the extractor (the cheap pre-filter is the main lever; add a hard cap).
- `[ckpt]` **T6.5 end-to-end smoke** — run the full path on a Discord server I control. *The live demo is the pitch.*

### M7 — Slice 8: Slack adapter (deferred, lowest priority)
- `[auto]` **T7.1** — second ingestion adapter on the same backend; same raw-store contract.

## The `/loop` runner

- **Ledger:** `docs/launch/PROGRESS.md` — every task with status (`pending` / `in-progress` / `done` / `blocked-ckpt`), in order, with its `[auto]`/`[ckpt]` tag.
- **Per pass (self-paced, one task):** read ledger → pick the next `pending` task → if `[auto]`, implement via TDD (`superpowers:test-driven-development`), run the suite, commit, mark `done`; if `[ckpt]`, mark `blocked-ckpt`, stop, and surface exactly what the human must do.
- **Checkpoints:** after each `[auto]` task the loop offers a review pause before continuing.
- **Stop conditions:** all `done`; or a `[ckpt]`/blocked task; or tests red after fix attempts (hand to `superpowers:systematic-debugging`).
- **Cheapness:** no agent fan-out — one focused task at a time, reviewed at each checkpoint.

## Out of scope (v1, per the original design spec)

Confidence-gated moderation, review queue, per-community pages, multi-language,
accounts/auth on the public site, Discord bot verification and Slack App Directory
listing (only when scale demands — Discord verification is required above ~75–100 servers).

## Open risks

- Airtable free-tier record cap (~1,200/base) is the first wall; Postgres migration path noted.
- Edge exclusion is the central trust guarantee and is **not built yet** — no external server should be onboarded before M3 lands.
- LLM cost — cheap pre-filter + a hard spend cap (T6.4).
- On-demand revalidation depends on the Airtable automation firing; the timed fallback bounds staleness.
