> **HISTORICAL** — this is the original approved design (2026-06-25), kept for provenance. The system as deployed is described in [`ARCHITECTURE.md`](../ARCHITECTURE.md); where they disagree, ARCHITECTURE.md wins.

# AI Safety Opportunities Aggregator — design spec

A public, auto-updating board of AI-safety opportunities (jobs, fellowships, grants, events, courses), fed by Discord/Slack communities that install an open-source bot into their own servers.

Status: design approved 2026-06-25, pre-implementation.

## Core idea

Community owners install a thin, open-source bot into their server and authorize specific channels. The bot forwards messages to a central backend. An LLM pipeline extracts genuine opportunities, dedupes them across communities, and publishes them near-real-time to a public website. The output is public by design, so there is no private data product to hide — that is the central trust argument.

Discord first (full message-history access, clean bot distribution). Slack is a later second ingestion adapter on the same backend.

## Locked decisions

- **Install model:** owners install the bot themselves via OAuth — legitimate and ToS-compliant, no personal-token scraping.
- **Processing model A:** raw firehose to the backend, all intelligence central. Installed bot stays dumb so logic can be retuned without redeploying to every server.
- **Canonical store:** Airtable (store + working view + backs the site). Migrate to Postgres if it outgrows free-tier limits (~1,200 records/base, rate limits).
- **Moderation:** auto-publish + fast takedown, with one guard — the link-safety gate withholds suspicious items.
- **Freshness:** near-real-time, event-driven (the Discord gateway connection is already always-on).
- **Backend host:** Railway or Fly.io (always-on container). Website on Vercel.
- **Transparency:** open-source thin bot AND backend, single public monorepo. Secrets in env vars only — nothing committed, `.env.example` with blank placeholders. MIT license. Plain-English data policy.
- **Privacy filtering happens at the edge** (in the bot, before transmit) — the strongest guarantee is that excluded messages never leave the server.

## Data flow

```
[Installed Discord bot] --> backend (ingestion API) --> raw store --> cheap filter
   |  edge exclusion check                                              |
   |  runs BEFORE transmit                                              v
   |                                        PII strip --> link-safety gate --> LLM extract
   |                                                                        |
   |                                                  dedup (update, not just drop)
   |                                                                        v
   |                                                  Airtable --> public site (Vercel)
   |                                                                  |  RSS + search/filter
   +-- lock-reaction / [private] edit ------ DELETE from site <-------+
```

## Components

Each is independently understandable and testable.

- **Discord bot (thin client).** Holds the gateway connection; receives messages; runs the edge exclusion check; forwards survivors; listens for the lock-emoji reaction / `[private]` edits to signal deletes; tracks a per-channel last-seen cursor for downtime backfill. No classification logic. Open-source.
- **Ingestion API (backend).** One endpoint the bot posts to; writes raw messages verbatim; multi-tenant (knows which server/channel each message came from). Open-source.
- **Extraction pipeline.** (a) cheap first-pass filter (keyword/heuristic or small model: "plausibly an opportunity?"); (b) PII strip — normalize "DM me / email me" to the official link, drop personal contact details; (c) link-safety gate — withhold suspicious / brand-new-domain / known-bad links; (d) LLM extraction into structured fields; (e) dedup against existing records via a stable key (application URL, else org+title+deadline), updating the existing record when a newer version appears. Open-source.
- **Canonical store (Airtable).** One record per opportunity. Source of truth + working view.
- **Public website (Vercel).** Reads Airtable; list + search + filter (type / deadline / remote); RSS feed; demotes/hides expired items; rebuilds on change.
- **Status/expiry job.** Daily scheduled re-evaluation of deadline `status` (`active` / `closing-soon` / `expired`).
- **Email digest.** Subscribe form on the site, subscriber list, sending service (e.g. Resend or Buttondown), scheduled digest. Stores subscriber emails — needs a privacy-policy line and unsubscribe link.
- **Install config.** Captured at OAuth: which channels, and each channel's public-default vs private-default.

## Data model (Airtable record)

`title`, `org`, `type`, `deadline`, `status`, `link`, `source_server`, `source_channel`, `raw_text`, `date_seen`.

`type` vocabulary: `job | internship | fellowship | grant | event | course | reading-group | other`.

## Privacy and exclusion

- **Edge exclusion:** bot drops, and never transmits, anything matching a documented vocabulary (`[private]`, `school-specific`, `internal`, `do-not-share`) OR posted in a private-default channel. Channel-level defaults mean sensitive channels fail closed even if a poster forgets the tag.
- **Retraction:** a designated lock-emoji reaction, or editing a message to add `[private]`, removes the item from the site. Also serves general takedowns. Works after posting, so something can be pulled back.
- **Optional quarantine delay:** publish N minutes after extraction so retractions can fire first. Off by default; flip on if a leak ever occurs.
- **Owner uninstall purges + visibility:** removing the bot purges that server's data; owner can see what has been ingested from their server.

## Safety against amplification

Auto-publish makes the system an amplifier for whatever is posted. Mitigations: the link-safety gate withholds suspicious items rather than auto-publishing them; PII stripping; the fast-takedown path; and the optional quarantine delay. This is the riskiest surface and gets the most guarding.

## Build order (Discord-first, incremental)

1. Bot to raw store (one server I control) + downtime backfill cursor.
2. Extraction pipeline: cheap filter -> PII strip -> link-safety gate -> extract -> dedup-with-update -> Airtable, with `type` + deadline `status`.
3. Public website: list + search/filter + RSS + expired handling.
4. Daily status/expiry job.
5. Installable OAuth bot: edge exclusion, channel defaults, retraction, uninstall purge + owner view.
6. Email digest: subscribe form + sender + scheduled job.
7. Legal pages (privacy / terms) — before public launch.
8. Slack adapter (later) — same backend, second ingestion path.

Build and prove the synthesis-to-site half first using a channel I already control, so there is a live demo running before pitching any owner — the demo is the pitch.

## Testing

Each unit tested in isolation: edge-exclusion (message -> drop/forward table), PII strip (input -> scrubbed), link-safety (link -> allow/withhold), extraction (sample messages -> expected fields), dedup (duplicates across servers -> single record, newer version -> updated record), retraction (signal -> record removed), backfill (cursor -> catch-up). Pipeline gets fixture messages end-to-end.

## Out of scope (v1)

Confidence-gated moderation, review queue, Obsidian mirror of the store, per-community pages, multi-language, accounts/auth on the public site, Slack App Directory listing and Discord bot verification (only when scale demands).

## Open risks to watch

- Slack install feasibility per workspace (admin vs member; scopes). Deferred but real.
- Airtable free-tier record cap is the first wall; Postgres migration path noted.
- LLM cost control — the cheap first-pass filter before expensive extraction is the main lever; add a spend cap.
- Discord bot verification required above ~75–100 servers.
