# Slack adapter — design

Date: 2026-07-07. Status: approved, pre-implementation.

Adds Slack as a second ingestion source for the opportunities board, per the
design spec's "Slack adapter (later) — same backend, second ingestion path."
Approach chosen: Events API routes inside the existing FastAPI backend
(no new process), with a `slackbot/` package holding the pure logic.

## Decisions (locked with owner)

- **Distribution:** self-serve, like Discord — any workspace admin uses an
  "Add to Slack" OAuth link. No manual onboarding path.
- **Channel consent:** the bot reads a channel only if it was `/invite`d into
  it **and** the channel name passes the existing name filter
  (`bot.scope.is_ingest_channel`, default needle `opportunities`). Inviting it
  to `#general` does nothing. Public channels only in v1; private channels
  (`groups:*` scopes) are out of scope.
- **Guarantee parity:** full. Live ingest, edge exclusion, 🔒-reaction and
  `[private]`-edit retraction, uninstall purge, and 14-day backfill all ship
  in v1 — the site's privacy promises are platform-unqualified.
- **Architecture:** Approach A — event receiver and OAuth routes mounted in
  `backend/app.py`; Slack needs no held gateway connection, and the OAuth
  redirect needs a public URL we already have. Rejected: a separate
  slack-bolt process (symmetry for its own sake on a 512MB machine) and
  Socket Mode (Slack steers distributed apps to the Events API, and it
  reintroduces a held websocket).

## Components

New package `slackbot/` (pure logic, mirrors `bot/`'s small-module style):

| Module | Responsibility |
|--------|----------------|
| `verify.py` | Slack request verification: `v0=` HMAC-SHA256 of `v0:<timestamp>:<body>` with the signing secret; reject timestamps older than ±5 minutes (replay guard). |
| `events.py` | Pure translators from Slack event payloads to pipeline actions — `message` → ingest; `message_changed` → retract when the new text carries an exclusion tag; `reaction_added` (`lock`) → retract; `member_joined_channel` (the bot itself) → backfill trigger; `app_uninstalled` / `tokens_revoked` → purge. Bot/system messages (`bot_id`, non-`message` subtypes other than `message_changed`) are ignored. |
| `tokens.py` | Per-workspace install store, SQLite on the existing `/data` Fly volume: `team_id`, `team_name`, `bot_token`, `installed_at`. Row deleted on uninstall/revocation. |
| `channels.py` | Channel-name resolution via `conversations.info`, cached; scope check = bot is a member AND `is_ingest_channel(name)`. |
| `backfill.py` | Triggered per channel when the bot is invited (at install time it is not yet in any channel): page `conversations.history` (`oldest` = now − 14 days, honoring `MAX_MESSAGE_AGE_DAYS`), run exclusion, ingest. |

Reused as-is: `bot/exclusion.py` (`should_exclude` is platform-neutral) and
`bot/scope.py`'s name filter. The worker, filter, LLM extraction, link
safety, dedupe, Airtable upsert, digest, and website are untouched — Slack
messages land in the same `RawStore` and flow through identically.

## Identity mapping

Slack IDs must not collide with Discord snowflakes, and Slack's `ts` is only
unique per channel:

- `server_id` = `slack:<team_id>`
- `message_id` = `slack:<team_id>:<channel_id>:<ts>`
- `server_name` = workspace name (site attribution unchanged)
- `author_id` = Slack user id (used only for the existing PII handling)

Retraction events carry channel + ts, so the retraction key reconstructs
exactly. Purge keys on `server_id`.

## HTTP surface (added to `backend/app.py`)

- `POST /slack/events` — handles the `url_verification` challenge; verifies
  the signature (401 on failure); ACKs within Slack's 3-second deadline.
  Verified events always return 200 even when ignored, so Slack does not
  auto-disable the app. Slack retries (`x-slack-retry-num`) are harmless:
  ingest is already idempotent by `message_id`.
- `GET /slack/install` — redirect to Slack's OAuth consent. Bot scopes:
  `channels:history`, `channels:read`, `reactions:read`, `team:read`.
- `GET /slack/oauth/callback` — exchange the code for a bot token, persist
  the install, and render a "you're installed — now /invite the bot to your
  opportunities channel" confirmation page (backfill starts on invite).

## Config

New env vars, documented in `.env.example`: `SLACK_CLIENT_ID`,
`SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`. Per-workspace bot tokens live
only in the SQLite install store, never in env or logs.

## Failure handling

- Signature failure → 401, no processing.
- Token revoked or app uninstalled → same purge path as Discord kick:
  delete the workspace's raw messages, published records, and install row.
- Backfill and `conversations.info` API errors → logged and retried on the
  next trigger; never crash the app process.
- No message content or tokens in logs (existing privacy invariant).

## Docs and policy updates (part of this work)

- Privacy page: Slack pushes events to us, so for Slack the exclusion
  guarantee reads "discarded at ingestion, before storage or processing"
  (Discord keeps the in-server wording).
- README: Slack install instructions alongside Discord's.

## Testing

- Pure-function tests: signature verification (good/bad/stale), event
  translation for every event type, ID mapping, backfill pagination and
  14-day cutoff, channel scope check.
- Route tests with FastAPI TestClient: challenge handshake, signed/unsigned
  events, OAuth callback happy path.
- Fake Slack WebClient (existing fake-client pattern in `tests/`) for
  backfill and channel resolution.

## Out of scope

Private Slack channels, Slack App Directory listing, per-workspace channel
configuration UI, message threading semantics (thread replies ingest as
plain messages), and Enterprise Grid.
