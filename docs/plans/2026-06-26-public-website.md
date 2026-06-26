# Public Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Next.js site on Vercel that reads the Airtable canonical store server-side and shows AI-safety opportunities — searchable, filterable, with an RSS feed — refreshing near-instantly via an on-demand revalidation webhook.

**Architecture:** Next.js App Router app in `web/`. Airtable is read **server-side only** (token never reaches the browser). The home page is statically generated (ISR) and refreshed by an Airtable-automation webhook hitting a secured `/api/revalidate` route, with a 1-hour timed fallback. Search/filter/sort run **client-side** over the pre-rendered list. Expired/closing-soon state is computed on the fly from each record's `deadline`. All logic lives in small pure modules (`lib/status`, `lib/airtable`, `lib/filter`, `lib/rss`) that are Vitest-tested; the page and components stay thin.

**Tech Stack:** Next.js (App Router, TypeScript), Tailwind, Vitest + @testing-library/react, plain `fetch` against the Airtable REST API. npm. Deployed to Vercel.

## Global Constraints

- Next.js App Router + TypeScript; npm as the package manager. All commands run from `web/`.
- Airtable is read **server-side only**. Airtable env vars (`AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`) and `REVALIDATE_SECRET` must NOT be prefixed `NEXT_PUBLIC_` and must never be referenced from a client component.
- Display status is computed on the fly via `deriveStatus(deadline)`; the site does NOT read the Airtable `status` field.
- Search/filter/sort happen client-side over the full pre-rendered list.
- Expired items hidden by default (shown, demoted, only when "show past" is on); items link directly out to `link` in a new tab (no per-item detail page); default sort is `deadline` ascending, no-deadline last, `date_seen` desc tiebreak.
- RSS feed contains non-expired opportunities (`active` + `closing-soon`).
- Tests use Vitest; pure modules are fully unit-tested. Test command: `npx vitest run` (or a specific file path) from `web/`.
- The `@/*` import alias resolves to the `web/` project root in both Next and Vitest.

---

### Task 1: Scaffold Next.js app + Vitest + Opportunity type

**Files:**
- Remove: `web/.gitkeep`
- Create (via `create-next-app`): the Next.js app under `web/`
- Create: `web/vitest.config.ts`, `web/vitest.setup.ts`, `web/lib/types.ts`, `web/lib/scaffold.test.ts`
- Modify: `web/package.json` (add the `test` script)

**Interfaces:**
- Consumes: nothing.
- Produces: a working Next.js + Vitest project where `npx vitest run` passes, and the `Opportunity` type / `OppType` union in `web/lib/types.ts`:
  ```ts
  export type OppType = "job" | "internship" | "fellowship" | "grant" | "event" | "course" | "reading-group" | "other";
  export interface Opportunity {
    title: string; org: string; type: OppType | string;
    deadline: string | null; link: string | null; location: string | null;
    remote: boolean; sourceServer: string; sourceChannel: string;
    dateSeen: string | null; dedupKey: string;
  }
  ```

- [ ] **Step 1: Scaffold the Next.js app**

Run from the repo root (`/Users/kaustubhkislay/aisafety-opportunities`):
```bash
rm -f web/.gitkeep
npx create-next-app@latest web --ts --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm --disable-git --yes
```
(If `create-next-app` refuses because `web/` is non-empty, ensure only `.gitkeep` was there and it was removed.)

- [ ] **Step 2: Add Vitest + testing-library dev dependencies**

Run from `web/`:
```bash
cd web
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 3: Add Vitest config + setup, the type, and a failing smoke test**

Create `web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: ["./vitest.setup.ts"] },
  resolve: { alias: { "@": fileURLToPath(new URL("./", import.meta.url)) } },
});
```

Create `web/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom";
```

Create `web/lib/types.ts`:
```ts
export type OppType =
  | "job" | "internship" | "fellowship" | "grant"
  | "event" | "course" | "reading-group" | "other";

export interface Opportunity {
  title: string;
  org: string;
  type: OppType | string;
  deadline: string | null;
  link: string | null;
  location: string | null;
  remote: boolean;
  sourceServer: string;
  sourceChannel: string;
  dateSeen: string | null;
  dedupKey: string;
}
```

Create `web/lib/scaffold.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import type { Opportunity } from "@/lib/types";

describe("scaffold", () => {
  it("Opportunity type is usable", () => {
    const o: Opportunity = {
      title: "t", org: "o", type: "job", deadline: null, link: null,
      location: null, remote: false, sourceServer: "s", sourceChannel: "c",
      dateSeen: null, dedupKey: "k",
    };
    expect(o.title).toBe("t");
  });
});
```

In `web/package.json`, add to the `"scripts"` object:
```json
    "test": "vitest run"
```

- [ ] **Step 4: Run the test**

Run from `web/`: `npx vitest run lib/scaffold.test.ts`
Expected: PASS (1 test). If `@/lib/types` fails to resolve, the alias in `vitest.config.ts` is wrong — fix it before continuing.

- [ ] **Step 5: Confirm the app builds**

Run from `web/`: `npm run build`
Expected: a successful production build (no type errors).

- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "feat: scaffold Next.js app with Vitest and Opportunity type"
```

---

### Task 2: `deriveStatus` — on-the-fly deadline status

**Files:**
- Create: `web/lib/status.ts`, `web/lib/status.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `type Status = "active" | "closing-soon" | "expired"` and `deriveStatus(deadline: string | null, now: Date) -> Status`. No/blank/invalid deadline → `active`; deadline date before `now`'s date → `expired`; within 7 days (inclusive, including today) → `closing-soon`; else `active`. Comparison is date-only in UTC.

- [ ] **Step 1: Write the failing test**

Create `web/lib/status.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { deriveStatus } from "@/lib/status";

const NOW = new Date("2026-06-26T12:00:00Z");

describe("deriveStatus", () => {
  it("no deadline is active", () => {
    expect(deriveStatus(null, NOW)).toBe("active");
  });
  it("past deadline is expired", () => {
    expect(deriveStatus("2026-06-25", NOW)).toBe("expired");
  });
  it("today is closing-soon", () => {
    expect(deriveStatus("2026-06-26", NOW)).toBe("closing-soon");
  });
  it("within 7 days is closing-soon", () => {
    expect(deriveStatus("2026-07-03", NOW)).toBe("closing-soon");
  });
  it("more than 7 days out is active", () => {
    expect(deriveStatus("2026-08-01", NOW)).toBe("active");
  });
  it("invalid deadline is active", () => {
    expect(deriveStatus("not-a-date", NOW)).toBe("active");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `web/`: `npx vitest run lib/status.test.ts`
Expected: FAIL (cannot resolve `@/lib/status`).

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/status.ts`:
```ts
export type Status = "active" | "closing-soon" | "expired";

const DAY_MS = 24 * 60 * 60 * 1000;

function dayUTC(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

export function deriveStatus(deadline: string | null, now: Date): Status {
  if (!deadline) return "active";
  const parsed = new Date(deadline);
  if (Number.isNaN(parsed.getTime())) return "active";
  const days = (dayUTC(parsed) - dayUTC(now)) / DAY_MS;
  if (days < 0) return "expired";
  if (days <= 7) return "closing-soon";
  return "active";
}
```

- [ ] **Step 4: Run test to verify it passes**

Run from `web/`: `npx vitest run lib/status.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/status.ts web/lib/status.test.ts
git commit -m "feat: deriveStatus for on-the-fly deadline status"
```

---

### Task 3: `lib/airtable` — server fetch + record mapping

**Files:**
- Create: `web/lib/airtable.ts`, `web/lib/airtable.test.ts`

**Interfaces:**
- Consumes: `Opportunity` (Task 1).
- Produces:
  - `mapRecord(fields: Record<string, unknown>) -> Opportunity` — maps Airtable field names to the typed model (`source_server`→`sourceServer`, `date_seen`→`dateSeen`, `dedup_key`→`dedupKey`; `remote`→boolean; missing string fields → `""` for required, `null` for nullable).
  - `fetchOpportunities(fetchImpl?: typeof fetch) -> Promise<Opportunity[]>` — pages through the Airtable REST API (`pageSize=100`, following `offset`), Authorization from `AIRTABLE_API_KEY`, base from `AIRTABLE_BASE_ID`, table from `AIRTABLE_TABLE_NAME` (default `"Opportunities"`); throws on a non-ok response. `fetchImpl` is injectable for tests (defaults to global `fetch`).

- [ ] **Step 1: Write the failing test**

Create `web/lib/airtable.test.ts`:
```ts
import { describe, it, expect, beforeEach } from "vitest";
import { mapRecord, fetchOpportunities } from "@/lib/airtable";

describe("mapRecord", () => {
  it("maps Airtable fields to the typed model", () => {
    const o = mapRecord({
      title: "ML Fellow", org: "Redwood", type: "fellowship",
      deadline: "2026-08-01", link: "https://x.org/apply", location: "Remote",
      remote: true, source_server: "srv", source_channel: "jobs",
      date_seen: "2026-06-26", dedup_key: "url:x.org/apply",
    });
    expect(o.org).toBe("Redwood");
    expect(o.remote).toBe(true);
    expect(o.sourceServer).toBe("srv");
    expect(o.dateSeen).toBe("2026-06-26");
    expect(o.dedupKey).toBe("url:x.org/apply");
  });
  it("defaults missing fields (null for nullable, '' for required, false for remote)", () => {
    const o = mapRecord({ title: "t", org: "o", type: "job" });
    expect(o.deadline).toBeNull();
    expect(o.link).toBeNull();
    expect(o.location).toBeNull();
    expect(o.remote).toBe(false);
    expect(o.dedupKey).toBe("");
  });
});

describe("fetchOpportunities", () => {
  beforeEach(() => {
    process.env.AIRTABLE_API_KEY = "key";
    process.env.AIRTABLE_BASE_ID = "appX";
    process.env.AIRTABLE_TABLE_NAME = "Opportunities";
  });

  it("follows pagination and maps all records", async () => {
    const pages = [
      { records: [{ fields: { title: "A", org: "o", type: "job" } }], offset: "p2" },
      { records: [{ fields: { title: "B", org: "o", type: "job" } }] },
    ];
    let call = 0;
    const fakeFetch = async () => ({
      ok: true,
      status: 200,
      json: async () => pages[call++],
    }) as unknown as Response;

    const result = await fetchOpportunities(fakeFetch as unknown as typeof fetch);
    expect(result.map((r) => r.title)).toEqual(["A", "B"]);
  });

  it("throws on a non-ok response", async () => {
    const fakeFetch = async () => ({ ok: false, status: 429, json: async () => ({}) }) as unknown as Response;
    await expect(fetchOpportunities(fakeFetch as unknown as typeof fetch)).rejects.toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `web/`: `npx vitest run lib/airtable.test.ts`
Expected: FAIL (cannot resolve `@/lib/airtable`).

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/airtable.ts`:
```ts
import type { Opportunity } from "@/lib/types";

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}
function strOrNull(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

export function mapRecord(fields: Record<string, unknown>): Opportunity {
  return {
    title: str(fields.title),
    org: str(fields.org),
    type: str(fields.type) || "other",
    deadline: strOrNull(fields.deadline),
    link: strOrNull(fields.link),
    location: strOrNull(fields.location),
    remote: Boolean(fields.remote),
    sourceServer: str(fields.source_server),
    sourceChannel: str(fields.source_channel),
    dateSeen: strOrNull(fields.date_seen),
    dedupKey: str(fields.dedup_key),
  };
}

interface AirtablePage {
  records: { fields: Record<string, unknown> }[];
  offset?: string;
}

export async function fetchOpportunities(
  fetchImpl: typeof fetch = fetch,
): Promise<Opportunity[]> {
  const key = process.env.AIRTABLE_API_KEY;
  const base = process.env.AIRTABLE_BASE_ID;
  const table = process.env.AIRTABLE_TABLE_NAME ?? "Opportunities";
  if (!key || !base) throw new Error("Airtable env not configured");

  const out: Opportunity[] = [];
  let offset: string | undefined;
  do {
    const url = new URL(`https://api.airtable.com/v0/${base}/${encodeURIComponent(table)}`);
    url.searchParams.set("pageSize", "100");
    if (offset) url.searchParams.set("offset", offset);
    const res = await fetchImpl(url.toString(), {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (!res.ok) throw new Error(`Airtable request failed: ${res.status}`);
    const data = (await res.json()) as AirtablePage;
    for (const rec of data.records) out.push(mapRecord(rec.fields));
    offset = data.offset;
  } while (offset);
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run from `web/`: `npx vitest run lib/airtable.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/airtable.ts web/lib/airtable.test.ts
git commit -m "feat: Airtable server fetch + record mapping"
```

---

### Task 4: `lib/filter` — client-side filter + sort

**Files:**
- Create: `web/lib/filter.ts`, `web/lib/filter.test.ts`

**Interfaces:**
- Consumes: `Opportunity` (Task 1), `deriveStatus` (Task 2).
- Produces: `interface Query { text?: string; types?: string[]; remoteOnly?: boolean; showPast?: boolean }` and `filterAndSort(items: Opportunity[], query: Query, now: Date) -> Opportunity[]`. Text matches title/org case-insensitively; `types` (when non-empty) keeps matching `type`; `remoteOnly` keeps `remote`; expired items dropped unless `showPast`. Sort: deadline asc, items with no deadline after dated ones, `dateSeen` desc as tiebreak.

- [ ] **Step 1: Write the failing test**

Create `web/lib/filter.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { filterAndSort } from "@/lib/filter";
import type { Opportunity } from "@/lib/types";

const NOW = new Date("2026-06-26T12:00:00Z");

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: null, link: null, location: null,
    remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "",
    ...p,
  };
}

describe("filterAndSort", () => {
  it("text search matches title or org", () => {
    const items = [opp({ title: "Redwood Fellow" }), opp({ title: "Other", org: "Anthropic" })];
    expect(filterAndSort(items, { text: "redwood" }, NOW).map((o) => o.title)).toEqual(["Redwood Fellow"]);
    expect(filterAndSort(items, { text: "anthropic" }, NOW).map((o) => o.title)).toEqual(["Other"]);
  });
  it("type filter keeps only matching types", () => {
    const items = [opp({ title: "J", type: "job" }), opp({ title: "F", type: "fellowship" })];
    expect(filterAndSort(items, { types: ["fellowship"] }, NOW).map((o) => o.title)).toEqual(["F"]);
  });
  it("remoteOnly keeps only remote", () => {
    const items = [opp({ title: "R", remote: true }), opp({ title: "L", remote: false })];
    expect(filterAndSort(items, { remoteOnly: true }, NOW).map((o) => o.title)).toEqual(["R"]);
  });
  it("hides expired unless showPast", () => {
    const items = [opp({ title: "Old", deadline: "2026-01-01" }), opp({ title: "New", deadline: "2026-12-01" })];
    expect(filterAndSort(items, {}, NOW).map((o) => o.title)).toEqual(["New"]);
    expect(filterAndSort(items, { showPast: true }, NOW).map((o) => o.title).sort()).toEqual(["New", "Old"]);
  });
  it("sorts deadline asc, no-deadline last, dateSeen desc tiebreak", () => {
    const items = [
      opp({ title: "NoDeadlineA", deadline: null, dateSeen: "2026-06-01" }),
      opp({ title: "NoDeadlineB", deadline: null, dateSeen: "2026-06-20" }),
      opp({ title: "Soon", deadline: "2026-07-01" }),
      opp({ title: "Later", deadline: "2026-09-01" }),
    ];
    expect(filterAndSort(items, {}, NOW).map((o) => o.title)).toEqual(["Soon", "Later", "NoDeadlineB", "NoDeadlineA"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `web/`: `npx vitest run lib/filter.test.ts`
Expected: FAIL (cannot resolve `@/lib/filter`).

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/filter.ts`:
```ts
import type { Opportunity } from "@/lib/types";
import { deriveStatus } from "@/lib/status";

export interface Query {
  text?: string;
  types?: string[];
  remoteOnly?: boolean;
  showPast?: boolean;
}

export function filterAndSort(items: Opportunity[], query: Query, now: Date): Opportunity[] {
  const text = (query.text ?? "").trim().toLowerCase();
  const types = query.types ?? [];

  const filtered = items.filter((o) => {
    if (text && !`${o.title} ${o.org}`.toLowerCase().includes(text)) return false;
    if (types.length > 0 && !types.includes(o.type)) return false;
    if (query.remoteOnly && !o.remote) return false;
    if (!query.showPast && deriveStatus(o.deadline, now) === "expired") return false;
    return true;
  });

  return filtered.sort((a, b) => {
    if (a.deadline && b.deadline) {
      if (a.deadline !== b.deadline) return a.deadline < b.deadline ? -1 : 1;
    } else if (a.deadline && !b.deadline) {
      return -1;
    } else if (!a.deadline && b.deadline) {
      return 1;
    }
    const as = a.dateSeen ?? "";
    const bs = b.dateSeen ?? "";
    return as > bs ? -1 : as < bs ? 1 : 0;
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run from `web/`: `npx vitest run lib/filter.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/filter.ts web/lib/filter.test.ts
git commit -m "feat: client-side filter and sort"
```

---

### Task 5: `lib/rss` — RSS XML generation

**Files:**
- Create: `web/lib/rss.ts`, `web/lib/rss.test.ts`

**Interfaces:**
- Consumes: `Opportunity` (Task 1).
- Produces: `toRss(items: Opportunity[], siteUrl: string) -> string` returning well-formed RSS 2.0 XML. Each item's `<link>` is the opportunity `link` (or `siteUrl` if null), `<guid isPermaLink="false">` is the `dedupKey` (or link), title is `"title — org"`, description joins type / location / deadline. All text is XML-escaped. Zero items still yields valid XML.

- [ ] **Step 1: Write the failing test**

Create `web/lib/rss.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { toRss } from "@/lib/rss";
import type { Opportunity } from "@/lib/types";

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: null, link: null, location: null,
    remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "",
    ...p,
  };
}

describe("toRss", () => {
  it("empty list is still valid RSS", () => {
    const xml = toRss([], "https://site.example");
    expect(xml).toContain('<?xml version="1.0"');
    expect(xml).toContain("<rss version=\"2.0\">");
    expect(xml).toContain("</rss>");
    expect(xml).not.toContain("<item>");
  });
  it("renders an item with link and guid", () => {
    const xml = toRss([opp({ title: "ML Fellow", org: "Redwood", link: "https://x.org/a", dedupKey: "url:x.org/a" })], "https://site.example");
    expect(xml).toContain("<item>");
    expect(xml).toContain("ML Fellow — Redwood");
    expect(xml).toContain("<link>https://x.org/a</link>");
    expect(xml).toContain('<guid isPermaLink="false">url:x.org/a</guid>');
  });
  it("escapes XML-special characters", () => {
    const xml = toRss([opp({ title: "A & B <C>", org: "O" })], "https://site.example");
    expect(xml).toContain("A &amp; B &lt;C&gt;");
    expect(xml).not.toContain("A & B <C>");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `web/`: `npx vitest run lib/rss.test.ts`
Expected: FAIL (cannot resolve `@/lib/rss`).

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/rss.ts`:
```ts
import type { Opportunity } from "@/lib/types";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function toRss(items: Opportunity[], siteUrl: string): string {
  const entries = items
    .map((o) => {
      const link = o.link ?? siteUrl;
      const title = esc(o.org ? `${o.title} — ${o.org}` : o.title);
      const desc = esc(
        [o.type, o.location, o.deadline ? `deadline ${o.deadline}` : null]
          .filter(Boolean)
          .join(" · "),
      );
      const guid = esc(o.dedupKey || link);
      return `    <item><title>${title}</title><link>${esc(link)}</link><guid isPermaLink="false">${guid}</guid><description>${desc}</description></item>`;
    })
    .join("\n");

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0"><channel>',
    "<title>AI Safety Opportunities</title>",
    `<link>${esc(siteUrl)}</link>`,
    "<description>Opportunities in AI safety</description>",
    entries,
    "</channel></rss>",
  ].join("\n");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run from `web/`: `npx vitest run lib/rss.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/rss.ts web/lib/rss.test.ts
git commit -m "feat: RSS XML generation"
```

---

### Task 6: Route handlers — RSS feed + secured revalidate webhook

**Files:**
- Create: `web/app/feed.xml/route.ts`, `web/app/api/revalidate/route.ts`, `web/app/api/revalidate/route.test.ts`

**Interfaces:**
- Consumes: `fetchOpportunities` (Task 3), `deriveStatus` (Task 2), `toRss` (Task 5).
- Produces:
  - `GET` at `/feed.xml` — fetches opportunities, drops expired, returns `toRss(nonExpired, SITE_URL)` with `Content-Type: application/rss+xml; charset=utf-8`.
  - `POST` at `/api/revalidate` — reads `?secret=`; if it doesn't match `REVALIDATE_SECRET` (or is missing) → `401`; otherwise calls `revalidatePath("/")` and `revalidatePath("/feed.xml")` and returns `{ revalidated: true }`.

- [ ] **Step 1: Write the failing test (revalidate route)**

Create `web/app/api/revalidate/route.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// vi.hoisted ensures the mock fn exists in the hoisted scope the factory runs in
const { revalidatePath } = vi.hoisted(() => ({ revalidatePath: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath }));

import { POST } from "@/app/api/revalidate/route";

describe("POST /api/revalidate", () => {
  beforeEach(() => {
    revalidatePath.mockClear();
    process.env.REVALIDATE_SECRET = "s3cret";
  });

  it("rejects a missing secret with 401", async () => {
    const res = await POST(new Request("https://site.example/api/revalidate", { method: "POST" }));
    expect(res.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
  it("rejects a wrong secret with 401", async () => {
    const res = await POST(new Request("https://site.example/api/revalidate?secret=wrong", { method: "POST" }));
    expect(res.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
  it("revalidates on a valid secret", async () => {
    const res = await POST(new Request("https://site.example/api/revalidate?secret=s3cret", { method: "POST" }));
    expect(res.status).toBe(200);
    expect(revalidatePath).toHaveBeenCalledWith("/");
    expect(revalidatePath).toHaveBeenCalledWith("/feed.xml");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `web/`: `npx vitest run app/api/revalidate/route.test.ts`
Expected: FAIL (cannot resolve `@/app/api/revalidate/route`).

- [ ] **Step 3: Write the revalidate route**

Create `web/app/api/revalidate/route.ts`:
```ts
import { revalidatePath } from "next/cache";

export async function POST(req: Request): Promise<Response> {
  const secret = new URL(req.url).searchParams.get("secret");
  const expected = process.env.REVALIDATE_SECRET;
  if (!expected || secret !== expected) {
    return new Response("unauthorized", { status: 401 });
  }
  revalidatePath("/");
  revalidatePath("/feed.xml");
  return Response.json({ revalidated: true });
}
```

- [ ] **Step 4: Write the feed route**

Create `web/app/feed.xml/route.ts`:
```ts
import { fetchOpportunities } from "@/lib/airtable";
import { deriveStatus } from "@/lib/status";
import { toRss } from "@/lib/rss";

export const revalidate = 3600;

export async function GET(): Promise<Response> {
  const now = new Date();
  const items = (await fetchOpportunities()).filter(
    (o) => deriveStatus(o.deadline, now) !== "expired",
  );
  const siteUrl = process.env.SITE_URL ?? "https://example.com";
  return new Response(toRss(items, siteUrl), {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run from `web/`: `npx vitest run app/api/revalidate/route.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add web/app/feed.xml/route.ts web/app/api/revalidate/route.ts web/app/api/revalidate/route.test.ts
git commit -m "feat: RSS feed route + secured revalidate webhook"
```

---

### Task 7: UI — home page + opportunity list

**Files:**
- Create: `web/app/opportunity-list.tsx`, `web/app/opportunity-list.test.tsx`
- Modify: `web/app/page.tsx` (replace the create-next-app default)

**Interfaces:**
- Consumes: `Opportunity` (Task 1), `filterAndSort`/`Query` (Task 4), `deriveStatus` (Task 2), `fetchOpportunities` (Task 3).
- Produces:
  - `OpportunityList({ opportunities, nowISO }: { opportunities: Opportunity[]; nowISO: string })` — a client component with a search box, a remote-only toggle, a show-past toggle, and a type `<select>`; it renders the `filterAndSort` result as a list. Each item shows the title (an `<a href={link} target="_blank">` when `link` is set), org, type, location, and a relative deadline label; `closing-soon` gets an accent and `expired` is greyed.
  - `web/app/page.tsx` — async server component: `const opportunities = await fetchOpportunities()` then `<OpportunityList opportunities={opportunities} nowISO={new Date().toISOString()} />`, with `export const revalidate = 3600`, a header, and a footer with a placeholder privacy link.

- [ ] **Step 1: Write the failing test**

Create `web/app/opportunity-list.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OpportunityList } from "@/app/opportunity-list";
import type { Opportunity } from "@/lib/types";

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: "2027-01-01", link: "https://x.org",
    location: null, remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "",
    ...p,
  };
}

const NOW_ISO = "2026-06-26T12:00:00Z";

describe("OpportunityList", () => {
  it("renders opportunities and filters by search text", async () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "Redwood Fellow" }), opp({ title: "Anthropic SWE" })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByText("Redwood Fellow")).toBeInTheDocument();
    expect(screen.getByText("Anthropic SWE")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox"), "redwood");
    expect(screen.getByText("Redwood Fellow")).toBeInTheDocument();
    expect(screen.queryByText("Anthropic SWE")).not.toBeInTheDocument();
  });

  it("links the title out to the application URL", () => {
    render(<OpportunityList opportunities={[opp({ title: "ML Fellow", link: "https://apply.example/x" })]} nowISO={NOW_ISO} />);
    const link = screen.getByRole("link", { name: /ML Fellow/ });
    expect(link).toHaveAttribute("href", "https://apply.example/x");
    expect(link).toHaveAttribute("target", "_blank");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `web/`: `npx vitest run app/opportunity-list.test.tsx`
Expected: FAIL (cannot resolve `@/app/opportunity-list`).

- [ ] **Step 3: Write the client component**

Create `web/app/opportunity-list.tsx`:
```tsx
"use client";

import { useMemo, useState } from "react";
import type { Opportunity, OppType } from "@/lib/types";
import { filterAndSort } from "@/lib/filter";
import { deriveStatus } from "@/lib/status";

const TYPES: OppType[] = [
  "job", "internship", "fellowship", "grant", "event", "course", "reading-group", "other",
];

function deadlineLabel(deadline: string | null, now: Date): string {
  if (!deadline) return "no deadline";
  const status = deriveStatus(deadline, now);
  if (status === "expired") return "closed";
  return `closes ${deadline}`;
}

export function OpportunityList({
  opportunities,
  nowISO,
}: {
  opportunities: Opportunity[];
  nowISO: string;
}) {
  const now = new Date(nowISO);
  const [text, setText] = useState("");
  const [type, setType] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [showPast, setShowPast] = useState(false);

  const visible = useMemo(
    () =>
      filterAndSort(
        opportunities,
        { text, types: type ? [type] : [], remoteOnly, showPast },
        now,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opportunities, text, type, remoteOnly, showPast, nowISO],
  );

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="search"
          placeholder="Search title or org…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="border rounded px-3 py-2 flex-1 min-w-[12rem]"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="border rounded px-3 py-2"
          aria-label="Filter by type"
        >
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} />
          Show past
        </label>
      </div>

      <ul className="space-y-4">
        {visible.map((o) => {
          const status = deriveStatus(o.deadline, now);
          return (
            <li
              key={o.dedupKey || `${o.title}-${o.link}`}
              className={`border rounded p-4 ${status === "expired" ? "opacity-50" : ""} ${status === "closing-soon" ? "border-amber-400" : ""}`}
            >
              <h2 className="font-semibold">
                {o.link ? (
                  <a href={o.link} target="_blank" rel="noopener noreferrer" className="underline">
                    {o.title}
                  </a>
                ) : (
                  o.title
                )}
              </h2>
              <p className="text-sm text-gray-600">
                {o.org} · {o.type}
                {o.location ? ` · ${o.location}` : ""}
                {o.remote ? " · remote" : ""}
              </p>
              <p className="text-sm">{deadlineLabel(o.deadline, now)}</p>
            </li>
          );
        })}
      </ul>
      {visible.length === 0 && <p className="text-gray-500">No opportunities match.</p>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run from `web/`: `npx vitest run app/opportunity-list.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Write the home page**

Replace the entire contents of `web/app/page.tsx` with:
```tsx
import { fetchOpportunities } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";

export const revalidate = 3600;

export default async function Home() {
  const opportunities = await fetchOpportunities();
  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">AI Safety Opportunities</h1>
        <p className="text-gray-600">
          Jobs, fellowships, grants, events, and courses in AI safety.{" "}
          <a href="/feed.xml" className="underline">RSS</a>
        </p>
      </header>
      <OpportunityList opportunities={opportunities} nowISO={new Date().toISOString()} />
      <footer className="mt-12 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a>
      </footer>
    </main>
  );
}
```

- [ ] **Step 6: Run the full suite + build**

Run from `web/`:
```bash
npx vitest run
npm run build
```
Expected: all Vitest tests pass; production build succeeds (no type errors).

> Note: `npm run build` will statically prerender `/` and `/feed.xml`, which call `fetchOpportunities()`. If `AIRTABLE_*` env vars are not set in the build environment, those routes throw at build time. For the local build check, either export the `AIRTABLE_*` vars (the values are in the repo root `.env`) or set `export const dynamic = "force-dynamic"` is NOT desired — instead run the build with the env present: `set -a; . ../.env; set +a; npm run build`. On Vercel the env vars are configured in the dashboard, so prerender succeeds there.

- [ ] **Step 7: Commit**

```bash
git add web/app/opportunity-list.tsx web/app/opportunity-list.test.tsx web/app/page.tsx
git commit -m "feat: home page and opportunity list UI"
```

---

## Manual verification + deploy (after all tasks)

1. From `web/`, run locally with env loaded: `set -a; . ../.env; set +a; npm run dev`, open `http://localhost:3000` — confirm the list renders from the live Airtable base (seed a record first via the Slice-2 worker, or add one in Airtable), search/filters work, and `/feed.xml` returns RSS.
2. Deploy to Vercel (via the connected Vercel integration or `vercel` CLI). Set env vars in the Vercel dashboard: `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`, `REVALIDATE_SECRET`, `SITE_URL` (the deployed URL).
3. In Airtable, add an automation: "When a record is created or updated in Opportunities → run a script / send webhook" → `POST https://<site>/api/revalidate?secret=<REVALIDATE_SECRET>`.
4. Verify: edit a record in Airtable → within seconds the site reflects it (on-demand revalidation); if the webhook is removed, the change still appears within the 1-hour fallback.

## Out of scope for this plan (later slices)

Email digest + subscribe form (Slice 6); legal/privacy page content (footer links to `/privacy`, a stub page is a later step); accounts/auth; per-community pages; the daily deadline-status job (status computed on the fly); analytics; server-side filtering/pagination; visual polish beyond a clean, scannable Tailwind layout (a dedicated design pass can use the hallmark skill).
