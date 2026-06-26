# Slice 3 — Public website — design spec

The public face of the aggregator: a Next.js site on Vercel that reads the Airtable canonical store and shows AI-safety opportunities — searchable, filterable, with an RSS feed — refreshing near-instantly as the extraction worker writes new records.

Status: design approved 2026-06-26, pre-implementation. Independent of the Python backend (Slices 1–2) — reads Airtable directly. Branches off `main`.

## Core idea

A statically-generated (ISR) Next.js App Router site reads all opportunities from Airtable **server-side** (the token never reaches the browser) and renders a single scannable list page. Search, type/remote filters, and a show-past toggle run **client-side** over the pre-rendered data (instant, no per-keystroke API calls). Expired/closing-soon state is computed on the fly from each record's `deadline`, so the site does not depend on the daily-status job. The page (and an RSS feed) refresh near-instantly via an on-demand revalidation webhook that an Airtable automation calls whenever a record changes, with a timed revalidation as a safety net.

## Locked decisions

- **Framework:** Next.js (App Router), deployed to Vercel.
- **Freshness:** ISR + on-demand revalidation. An Airtable automation pings a secured `/api/revalidate` route on record change → `revalidatePath`; a 1-hour timed revalidate is the fallback if a webhook is missed.
- **Airtable access:** server-side only via the REST API using plain `fetch` (no extra dependency). Token in a server env var, never exposed to the client.
- **Search/filter:** client-side over the full pre-rendered list (small dataset; pairs naturally with ISR). Server-side filtering deferred until the dataset outgrows it.
- **Expired handling:** display status computed on the fly from `deadline` (`active` / `closing-soon` = within 7 days / `expired`). Expired items are hidden by default and revealed (demoted/greyed) via a "show past" toggle. The site does not read the Airtable `status` field.
- **Item interaction:** each opportunity links directly out to its application `link` (new tab); no per-item detail page. Items without a link render without one.
- **Sort:** by `deadline` ascending (soonest first); items with no deadline after, then `date_seen` descending.
- **Styling:** Tailwind; clean, scannable, mobile-friendly, anti-AI-slop.
- **Tests:** Vitest for the pure modules (status, mapping, filter/sort, RSS) and the revalidate route.

## Data flow

```
Airtable ──(server fetch)──▶ lib/airtable ──▶ page.tsx (ISR static) ──▶ client list (search / filter / sort)
                                              └──▶ feed.xml/route (RSS of active opportunities)
Airtable record change ──▶ Airtable automation ──▶ /api/revalidate?secret=… ──▶ revalidatePath("/") + RSS
```

## Components

Each is small and independently testable.

- **`web/lib/airtable.ts`** (server-only) — `fetchOpportunities() -> Opportunity[]`: fetch records via Airtable REST (paginated `fetch`), map fields to a typed `Opportunity`. Token/base/table from server env (`AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`).
- **`web/lib/status.ts`** (pure) — `deriveStatus(deadline: string | null, now: Date) -> "active" | "closing-soon" | "expired"`. No deadline → `active`; deadline in the past → `expired`; within 7 days → `closing-soon`; else `active`.
- **`web/lib/filter.ts`** (pure) — `filterAndSort(items, query) -> Opportunity[]`: applies text search (title/org), type filter, remote filter, show-past toggle (drops expired unless enabled), and the deadline-asc / date_seen-desc sort.
- **`web/lib/rss.ts`** (pure) — `toRss(items) -> string`: builds valid RSS XML from the given opportunities (the feed route passes non-expired items — `active` + `closing-soon`).
- **`web/app/page.tsx`** (server component) — fetches via `lib/airtable`, renders the list shell + `OpportunityList`. ISR with the 1-hour fallback revalidate.
- **`web/app/opportunity-list.tsx`** (client component) — search box, type + remote filters, show-past toggle; calls `filterAndSort`; renders items linking out to `link`.
- **`web/app/feed.xml/route.ts`** (route handler) — fetches opportunities, drops expired ones (via `deriveStatus`), returns `toRss(nonExpired)` with `Content-Type: application/rss+xml`.
- **`web/app/api/revalidate/route.ts`** (route handler) — validates a shared secret (`REVALIDATE_SECRET`), calls `revalidatePath("/")` and the feed; bad/missing secret → 401.

## Typed model

`Opportunity` (TypeScript), mapped from Airtable:
`title, org, type, deadline (string|null), link (string|null), location (string|null), remote (boolean), source_server, source_channel, dateSeen, dedupKey`.
(`raw_text`, `llm_model`, and the Airtable `status` field are not consumed by the site.)

## Display

- One list/board page. Each item shows: title (links to `link`), org, type badge, a relative deadline ("closes in 5 days" / "closed"), location + a remote badge.
- `closing-soon` items get a subtle urgency accent; `expired` items (only when "show past" is on) are greyed and sorted last.
- Filters: free-text search (title/org), a type multi-select (the fixed vocab), a remote-only toggle, and the show-past toggle.
- Footer: a placeholder link slot for a future privacy/terms page (content is a later step).

## Error handling

- Airtable fetch failure during revalidation → ISR continues serving the last good static page (no blank site); the failure is logged.
- Missing/empty fields render gracefully (no crash on null `deadline`/`link`/`location`).
- `/api/revalidate` with a bad or missing secret → HTTP 401, no revalidation.
- RSS always returns valid XML, even with zero items.

## Testing

Pure units with fixtures:
- `deriveStatus`: deadline + now → status table (no-deadline, past, within-7-days, far-future).
- `lib/airtable` mapping: a fake Airtable JSON response → typed `Opportunity[]` (correct field/types, remote→boolean, missing fields → null).
- `filterAndSort`: text/type/remote/show-past combinations and the sort order (deadline asc, no-deadline last, date_seen desc tiebreak).
- `toRss`: records → well-formed RSS XML (items present, escaping, empty case).
- `/api/revalidate`: bad/missing secret → 401; valid secret → revalidation invoked.
The page and client component stay thin (logic lives in the pure modules).

## Build order (incremental)

1. Next.js app scaffold in `web/` (App Router, Tailwind, Vitest) + the `Opportunity` type.
2. `lib/status.ts` (pure).
3. `lib/airtable.ts` (server fetch + mapping, mocked in tests).
4. `lib/filter.ts` (filter + sort).
5. `lib/rss.ts` + `feed.xml` route.
6. `page.tsx` + `opportunity-list.tsx` (UI wiring; styling pass).
7. `api/revalidate` route (secured webhook).
8. Deploy to Vercel; set env vars; wire the Airtable automation → webhook.

## Out of scope (later slices)

Email digest + subscribe form (Slice 6); legal/privacy/terms page content (a later step — footer placeholder only here); accounts/auth; per-community pages; the daily deadline-status job (status computed on the fly here); analytics; server-side filtering/pagination (until the dataset requires it).

## Open risks to watch

- Airtable REST rate limits / pagination — `fetchOpportunities` must page through all records; fine at current scale, revisit with Postgres if the base outgrows Airtable.
- On-demand revalidation depends on an Airtable automation reliably calling the webhook; the timed fallback bounds staleness if it misfires.
- Public exposure of opportunity data is by design, but the site shows only the curated fields (not `raw_text`), keeping any residual PII in the verbatim audit copy out of the public page.
