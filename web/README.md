# web — public site

The public board for [aisafety-opportunities](../README.md): a Next.js (App Router) app that
renders curated opportunities from Airtable, with client-side filtering, an RSS feed, an email
digest subscribe form, and privacy/terms pages.

## How it works

- `app/page.tsx` — home page; statically rendered with ISR (`revalidate = 3600`), loads
  opportunities from Airtable at build/revalidate time.
- `app/feed.xml/route.ts` — RSS 2.0 feed (same ISR window).
- `app/api/subscribe/route.ts` — proxies digest signups to the backend (backend URL stays
  server-side).
- `app/api/revalidate/route.ts` — secret-guarded on-demand revalidation, hit by an Airtable
  automation on record change.
- `app/privacy` / `app/terms` — legal pages; copy must track actually-built behavior.
- `lib/` — Airtable fetch/mapping, filtering, status derivation, RSS building, subscribe
  validation. All unit-tested.

If Airtable is unreachable at build time, `loadOpportunities` degrades to an empty list so the
build never crashes; ISR keeps serving the last good page.

## Environment

| Var | Purpose |
|-----|---------|
| `AIRTABLE_API_KEY` / `AIRTABLE_BASE_ID` / `AIRTABLE_TABLE_NAME` | Opportunity source (table name defaults to `Opportunities`) |
| `SITE_URL` | Canonical site URL, used by the RSS feed |
| `BACKEND_URL` | Ingestion backend, for the subscribe proxy |
| `REVALIDATE_SECRET` | Shared secret for `POST /api/revalidate` |

## Develop

```bash
npm ci
npm test        # vitest
npm run dev     # http://localhost:3000
npm run build   # production build (works without Airtable env)
```

Note for agents: read `AGENTS.md` first — this Next.js version has breaking changes vs. common
knowledge; consult the vendored docs in `node_modules/next/dist/docs/`.
