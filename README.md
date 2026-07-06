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

The bot only reads channels an owner explicitly authorizes. Excluded/private messages never leave the server. Removing the bot purges that server's data. A full data policy will live in `docs/` before public launch.

## Secrets

Never commit tokens or keys. Copy `.env.example` to `.env` and fill it locally; `.env` is gitignored.

## License

MIT — see [`LICENSE`](LICENSE).
