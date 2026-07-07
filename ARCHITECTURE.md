# Architecture (current)

> This describes the system **as deployed**. The original design narrative is
> preserved in `docs/design-spec.md` (historical). Last full revision: 2026-07-07.

## Shape

A multi-platform opportunity aggregator with an event-pipeline core:

```
Discord bot (bot/) ─┐                                        ┌─► site (web/, Vercel, ISR)
                    ├─► privacy gate ─► raw log (raw.db) ─► LLM worker ─► Airtable ─┤
Slack app (slackbot/│   (bot/exclusion)   idempotent,       extract+classify        └─► daily digest (Resend)
 + backend/slack) ──┘                     tombstones        +enrich+dedup
```

The **trust contract** is the product: tagged messages (`[private]`,
`[uni-reserved]`, `school-specific`, `internal`, `do-not-share`) are dropped
*before transmit* in both adapters; 🔒 reactions / bracketed-tag edits retract
published items in seconds; uninstall purges everything a community
contributed, cursors included. PII stripping and link-safety guard the
publish side. All of it is enforced in code and covered by tests.

## Processes (one Fly.io machine, `deploy/entrypoint.sh`)

| Process | Entry | Role |
|---|---|---|
| API | `uvicorn backend.app` | `/ingest`, `/retract`, `/purge`, `/subscribe` (+confirm), `/unsubscribe`, `/ingested`, `/healthz`, and all `/slack/*` routes |
| Worker | `backend.worker` | polls raw log → filter → spend cap → LLM extract/classify → deadline enrichment → link safety → dedup → Airtable upsert → site revalidate |
| Discord bot | `bot.client` | gateway events, exclusion, backfill (14-day window, `opportunities` channels), retraction, guild-join/remove |
| Cron | supercronic | status job daily 09:00 UTC; digest daily 15:00 UTC (new items only, skips empty days) |

Any process death restarts the machine; every stage is idempotent/retryable,
which is what makes that safe.

## State

- `/data/raw.db` — messages (verbatim, tombstoned when processed/retracted) + per-channel cursors (server-stamped). Shared by API+worker+bot.
- `/data/subscribers.db` — digest subscribers (double-opt-in; `active` flag).
- `/data/slack_tokens.db` — per-workspace Slack bot tokens (never in env/logs).
- **Airtable** — the canonical published store (base `Opportunities`, 16 fields incl. `source_servers`, `source_message_id`, `categories`, `status`). The site reads it directly.
- All SQLite connections use WAL + 5s busy timeout via `backend/db.py`.

## Known load-bearing assumptions

1. **Exactly one worker.** `claim_unprocessed` is a plain SELECT — two worker replicas would double-process (and double-bill) every message.
2. **Airtable is small.** ~5 req/s ceiling; calls retry with backoff, but past a few hundred writes/day a Postgres migration is the planned exit.
3. **One machine, no redundancy** — deliberate minimal-ops; the healthcheck workflow (15-min probe → GitHub issue → owner email) is the pager.

## Operations

- **Deploys:** merge to `main` → GitHub Actions deploys Fly (backend paths) and Vercel deploys `web/`. No manual deploy exists.
- **Secrets:** `.env` (gitignored) is the owner's master copy; mirrored to Fly secrets + Vercel env. `slack_tokens.db` holds per-workspace tokens.
- **Monitoring:** `.github/workflows/healthcheck.yml` probes `/healthz`, the site, and the feed every 15 minutes; failures open a "production health" issue.
- **Spend safety:** `LLM_DAILY_CALL_CAP` bounds extraction+enrichment calls per UTC day.

## Module map

`backend/`: `app` (API), `slack` (Slack routes), `worker`, `extract` (LLM + classification), `enrich` (deadline from linked page), `filter` (cheap prefilter), `linksafety`, `dedup`, `airtable` (retrying backend), `store` (raw log), `subscribers`, `digest` (email build/send/tokens), `status_job`, `spend`, `revalidate`, `purge`, `feedback`→removed, `db` (SQLite settings), `models`.
`bot/`: `client`, `coordinator`, `backfill`, `forwarder`, `exclusion` (tag authority incl. `RETRACTION_TAGS`), `retraction`, `channel_config`, `scope`, `messages`, `config`.
`slackbot/`: `events` (event→action translation), `verify` (signatures + OAuth state), `tokens`, `channels` (scope cache), `backfill`, `ids` (cross-platform composite ids), `web` (Slack API client).
`web/`: see `web/README.md`.
