# Redistribution: sharing aggregated opportunities back to communities

Once opportunities are aggregated centrally, redistribute them to connected
communities that don't already have them — each community's #opportunities
channel becomes a two-way port: what they post flows out to everyone, and
what everyone else posts flows in.

## Decisions (defaults chosen in design discussion; user was AFK — revisit)

- **Cadence:** one daily digest post per community (skip empty days), not
  real-time. Mirrors the email digest; predictable and non-spammy.
- **Where + consent:** posts go to the same #opportunities channel the bot
  reads, but ONLY for communities that explicitly opt in. The read-only
  pitch is load-bearing for the trust contract, so redistribution is a
  separate, opt-in capability with its own permission grant.
- **Content:** everything live they don't have — new records whose
  `source_servers` does not include the community. Per-community filters
  (type/category/location) are v2.
- **Retraction:** propagates. If the origin retracts (🔒 / `[private]`
  edit / uninstall purge), redistributed copies are deleted everywhere.

## How "don't have it" is decided

A record's `source_servers` (Airtable, comma-joined) already unions every
community a deduped opportunity was seen in. A community "has" a record iff
its server/workspace name is in that union. Redistribution set for
community C = live records (status ≠ expired) published since the last
digest where C ∉ source_servers.

Self-echo safety: ingestion drops bot-authored messages on both platforms
(`slackbot/events.py` subtype/bot_id check; Discord equivalent), so the
bot's own digest posts can never be re-ingested. Add a regression test
pinning this, since redistribution turns that filter into a loop-breaker.

## Consent & permissions (the hard part)

Discord:
- Current install grants read-only permissions. Posting needs Send Messages
  (and Embed Links) — a NEW install URL with the extra permission bits.
- Opt-in flow: server admin re-authorizes via the new URL, then confirms in
  channel with a command (`@bot feed on` / slash command) or via a config
  message. Store consent per guild.

Slack:
- Current scopes are read-only (`channels:history,channels:read,
  reactions:read,team:read`). Posting needs `chat:write`.
- Slack supports incremental scope upgrades through the same OAuth flow:
  a "Enable the feed" link hits `/slack/install?feed=1` requesting the
  wider scope set; on callback, record feed consent for that workspace.
- The bot must be a member of the channel to post (it already is — it
  reads there).

Both platforms: consent is per-community, stored server-side, revocable
(`feed off` / re-run flow), and the /partners page copy is updated so the
trust story stays accurate: "read-only by default; communities can opt in
to receive the shared feed."

## Architecture

New module `backend/redistribute.py`, run by supercronic once daily
(offset from the email digest, e.g. 15:30 UTC), same single-process
constraints as everything else:

```
Airtable (live records) ──► diff vs source_servers ──► per-community batch
                                                        │
feeds.db: subscriptions ────────────────────────────────┤
          deliveries ledger ◄── post via Discord/Slack ◄┘
```

Components:
- **`feeds.db`** (new SQLite on /data, WAL like the rest):
  - `subscriptions(server_id, platform, channel_id, enabled_at, enabled_by)`
  - `deliveries(dedup_key, server_id, platform, channel_id, message_id,
    posted_at)` — the ledger. Powers both idempotence (never repost the
    same record to the same community) and retraction (find copies to
    delete).
- **Digest composer:** compact per-day message — title (linked), org,
  type/category, deadline; N items max with a "see all on the site" link.
  Discord: one embed; Slack: block kit. Reuses `derive_status` and the
  digest's item-selection logic (`backend/digest.py` precedent).
- **Posters:** Discord REST post (the gateway bot's token already exists;
  it gains permission only in opted-in guilds), Slack `chat.postMessage`
  with the per-workspace token from `slack_tokens.db`.
- **Retraction hook:** the existing retract/purge paths (backend worker,
  `backend/slack.py` Retract/Purge) additionally look up `deliveries` by
  the record's dedup_key and delete the posted messages
  (`chat.delete` / Discord delete), then tombstone the ledger rows.
  Purge of community C also deletes C's subscription and any deliveries
  *to* C.

## Ordering & failure semantics

- The cron job is idempotent: it reads the ledger before posting, so a
  crash mid-run just resumes next day without duplicates.
- Post failures (missing permission, archived channel, rate limit) are
  logged at WARNING (visible in fly logs — INFO is suppressed in prod) and
  retried next run; after K consecutive permission failures the
  subscription auto-disables and the owner is notified via the health
  issue.
- Rate limits: at current scale (≤ tens of communities × 1 post/day) this
  is far below both platforms' limits; the ledger insert happens after a
  successful post (at-least-once with idempotence via ledger check, so
  worst case is a rare duplicate on crash between post and insert — noted,
  acceptable for v1).

## Trust-contract & docs changes

- README + /partners "Add your community": describe the feed as optional;
  read-only remains the default install.
- Privacy page: redistributed content is already public on the site; the
  feed adds no new data collection.
- ARCHITECTURE.md: new component section + the "exactly one worker"
  caveat extended to the cron job (it must not run concurrently with
  itself; supercronic guarantees this).

## Testing

- Unit: diff logic (has/hasn't by source_servers), ledger idempotence,
  digest composition, retraction deletes ledger rows, subscription
  enable/disable, auto-disable after K failures.
- Integration-ish: fake Slack/Discord web clients (existing test pattern
  for `slackbot/web.py`), assert posts + deletes.
- Loop regression: a bot-authored digest message translated through
  `slackbot/events.py` yields Drop.

## Phasing

1. **v1 (Slack-only is fine to start):** feeds.db, opt-in via scope
   upgrade link, daily digest post, ledger, retraction propagation.
   Slack first because consent/scopes are cleaner and YAIA/XLab are the
   fresh installs.
2. **v1.5 (Discord):** new install URL with Send Messages, `feed on/off`
   command, same ledger.
3. **v2:** per-community filters (type/category/location), maybe
   per-community cadence, delivery stats on /partners.

## Open questions (deferred, not blocking)

- Digest post identity: post as the bot with clear "shared via
  aisopportunities.com" attribution + origin community credit per item?
  (Leaning yes — credit strengthens the network story.)
- Should communities that only *receive* (never source) count as partners
  on the site? (Leaning: separate "receiving" list or badge.)
