# aisafety-opportunities

A public, auto-updating board of AI-safety opportunities — jobs, fellowships, grants, events, courses — fed by Discord (and later Slack) communities that install an open-source bot into their own servers.

**This whole project is open source on purpose.** We ask community owners to let our code read their channels, so the code that does the reading — and everything that happens to the data afterward — is auditable here. The output is public by design: everything that survives filtering becomes visible on the site. There is no private data product.

## How it works

```
Installed Discord bot ──► backend ──► raw store ──► filter + PII strip + link-safety
   │  (private/excluded messages                                      │
   │   are dropped IN the server,                                     ▼
   │   before anything is sent)                              LLM extract + dedupe
   │                                                                  │
   └── lock-reaction / [private] edit ── removes from site ◄── Airtable ──► public site
```

- The installed bot is a **thin client** — it forwards messages and runs the privacy/exclusion check locally. All extraction logic lives in the backend.
- Messages marked `[private]` / `[uni-reserved]` / `school-specific` / `internal` / `do-not-share`, or posted in a channel an owner sets private-by-default, are **never transmitted**.
- An LLM extracts genuine opportunities, strips personal contact info, withholds suspicious links, and dedupes across communities.

## Install the bot in your server (community owners)

Takes about two minutes. You need **Manage Server** permission.

1. **Have an opportunities channel.** The bot only reads channels whose name
   contains `opportunities` (e.g. `#opportunities`, `#ai-opportunities`).
   Everything else in your server is invisible to it — by design.
2. **Click the install link:**

   > **[Add AI Safety Opportunities bot](https://discord.com/oauth2/authorize?client_id=1523518596108652554&scope=bot&permissions=66560)**

   Pick your server and authorize. The bot asks for only two permissions —
   *View Channels* and *Read Message History*. It cannot post, manage, or
   delete anything.
3. **That's it.** Within a minute the bot backfills the last **14 days** of
   your opportunities channel; genuine opportunities appear on
   [aisopportunities.com](https://aisopportunities.com) about 20 seconds after
   they're posted (attributed to your community by name). Forwarded messages
   work too.

### Controlling what gets shared

- **Keep something off the site before posting:** include `[private]` or
  `[uni-reserved]` (or `school-specific` / `internal` / `do-not-share`)
  anywhere in the message. It is dropped inside your server and never
  transmitted.
- **Pull something back after posting:** react with 🔒, or edit the message to
  add `[private]` / `[uni-reserved]`. The published record is deleted and the
  site updates within seconds.
- **Leave entirely:** kick the bot. Every record, raw message, and bookmark
  from your server is purged immediately — uninstall means gone.

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
| `backend/` | Ingestion API + extraction pipeline |
| `web/` | Public website (Vercel) |
| `docs/` | Design spec and data policy |

See [`docs/design-spec.md`](docs/design-spec.md) for the full design.

## Status

**Live at [aisopportunities.com](https://aisopportunities.com)** (launched 2026-07-06). Discord-first; Slack support is a later adapter on the same backend. Backend runs on Fly.io; site on Vercel; merges to `main` auto-deploy both. End-to-end smoke test (publish, edge exclusion, retraction, purge, digest) passed 2026-07-05/06.

## Privacy

The bot only reads channels an owner explicitly authorizes. Excluded/private messages never leave the server. Removing the bot purges that server's data. The full policy lives at [aisopportunities.com/privacy](https://aisopportunities.com/privacy).

## Secrets

Never commit tokens or keys. Copy `.env.example` to `.env` and fill it locally; `.env` is gitignored.

## License

MIT — see [`LICENSE`](LICENSE).
