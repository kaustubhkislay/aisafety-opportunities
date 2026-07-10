# aisafety-opportunities

A public, auto-updating board of AI-safety opportunities — jobs, fellowships, grants, events, courses — fed by Discord and Slack communities that install an open-source, read-only bot into their own servers.

**This whole project is open source on purpose.** We ask community owners to let our code read their channels, so the code that does the reading — and everything that happens to the data afterward — is auditable here. The output is public by design: everything that survives filtering becomes visible on the site. There is no private data product.

## How it works

```
Installed Discord bot ─┐
                       ├─► backend ──► raw store ──► filter + PII strip + link-safety
Installed Slack app  ──┘                                              │
   │  (private/excluded messages                                      ▼
   │   are dropped before storage                            LLM extract + dedupe
   │   or processing)                                                 │
   └── lock-reaction / [private] edit ── removes from site ◄── Airtable ──► public site
```

- The installed bot is a **thin client** — it forwards messages and runs the privacy/exclusion check at the edge. All extraction logic lives in the backend, shared by both platforms.
- Messages marked `[private]` / `[uni-reserved]` / `school-specific` / `internal` / `do-not-share`, or posted in a channel an owner sets private-by-default, are **never transmitted**.
- An LLM extracts genuine opportunities, strips personal contact info, withholds suspicious links, and dedupes across communities.

## Install the bot in your community (Discord or Slack)

Takes about two minutes. You need **Manage Server** permission on Discord, or
the ability to install apps on Slack.

1. **Have an opportunities channel.** The bot only reads channels whose name
   contains `opportunities` (e.g. `#opportunities`, `#ai-opportunities`).
   Everything else in your community is invisible to it — by design.
2. **Click the install link for your platform:**

   > **[Add to Discord](https://discord.com/oauth2/authorize?client_id=1523518596108652554&scope=bot&permissions=66560)** — pick your server and authorize. The bot asks for
   > only two permissions — *View Channels* and *Read Message History*. It
   > cannot post, manage, or delete anything.
   >
   > **[Add to Slack](https://aisopportunities-backend.fly.dev/slack/install)** — authorize (read-only scopes on public channels),
   > then **`/invite` the bot** into your opportunities channel. Inviting it
   > to any other channel does nothing.

3. **That's it.** The bot backfills the last **14 days** of your
   opportunities channel; genuine opportunities appear on
   [aisopportunities.com](https://aisopportunities.com) about 20 seconds after
   they're posted (attributed to your community by name). Forwarded messages
   work too.

### Controlling what gets shared

- **Keep something off the site before posting:** include `[private]` or
  `[uni-reserved]` (or `school-specific` / `internal` / `do-not-share`)
  anywhere in the message and it is never published. On Discord the bot drops
  it inside your server, before anything is transmitted; on Slack, which
  pushes events to our backend, it is discarded at ingestion — before storage
  or processing.
- **Pull something back after posting:** react with 🔒, or edit the message to
  add `[private]` / `[uni-reserved]`. The published record is deleted and the
  site updates within seconds.
- **Leave entirely:** kick the bot (Discord) or uninstall the app (Slack).
  Every record and raw message from your community is purged immediately —
  uninstall means gone.

## Self-hosting your own instance

The hosted bot above feeds aisopportunities.com. To run the whole stack
yourself:

1. **Clone and install:** `git clone … && cd aisafety-opportunities && uv sync`
   (Python 3.12+, [uv](https://docs.astral.sh/uv/)).
2. **Create a Discord application** at discord.com/developers/applications:
   add a Bot, enable the **Message Content intent** (required), copy the bot
   token; from OAuth2 copy the client ID (install URL scope `bot`,
   permissions `66560`).
3. **Provision services:** an Airtable base with the `Opportunities` table
   (fields listed in `backend/worker.py:build_fields`, plus `status` and
   `source_servers`), an OpenAI-compatible LLM endpoint (we use
   DeepSeek via OpenRouter), and optionally Resend for the digest.
4. **Configure:** `cp .env.example .env` and fill it in — every variable is
   documented inline.
5. **Run locally:** `uv run uvicorn backend.app:app --port 3000` (API),
   `uv run python -m backend.worker` (extraction), `uv run python -m bot.client`
   (bot). Tests: `uv run pytest`.
6. **Deploy:** `deploy/` + `fly.toml` run everything on one Fly.io machine
   with a persistent volume (`fly launch` from the repo, set secrets from your
   `.env`, `fly deploy`); the site in `web/` deploys to Vercel with root
   directory `web`. `.github/workflows/` auto-deploys both on merge and
   health-checks production every 15 minutes.

## Repo layout

| Path | What |
|------|------|
| `bot/` | Thin Discord bot (gateway listener, edge exclusion, retraction) |
| `slackbot/` | Slack adapter (Events API translation, OAuth, per-workspace tokens) |
| `backend/` | Ingestion API + extraction pipeline |
| `web/` | Public website (Vercel) |
| `docs/` | Design specs + launch ledger (current architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)) |

Current architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md). Original design: [`docs/design-spec.md`](docs/design-spec.md) (historical).

## Status

**Live at [aisopportunities.com](https://aisopportunities.com)** (launched 2026-07-06). Discord and Slack ingestion are both live and in production use — Slack shipped 2026-07-07 as a second adapter on the same backend, and the first external Slack workspaces connected 2026-07-09. Seven partner communities currently feed the board (see [aisopportunities.com/partners](https://aisopportunities.com/partners)), with a daily email digest and an RSS feed (`/feed.xml`) on the distribution side. The site presents the board as a bulletin wall — searchable, with multi-select type/category/location filters and expandable cards. Backend runs on Fly.io; site on Vercel; merges to `main` auto-deploy both, gated by CI and a post-deploy health check. Next planned: redistributing aggregated opportunities back to opted-in communities ([design spec](docs/superpowers/specs/2026-07-10-redistribution-design.md)).

## Privacy

The bot only reads channels an owner explicitly authorizes. Excluded/private messages never leave the server. Removing the bot purges that server's data — cursors included. The full policy lives at [aisopportunities.com/privacy](https://aisopportunities.com/privacy).

## Secrets

Never commit tokens or keys. Copy `.env.example` to `.env` and fill it locally; `.env` is gitignored.

## License

MIT — see [`LICENSE`](LICENSE).
