# SEO Foundations (robots, sitemap, metadata) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give aisopportunities.com the crawler/indexing surface it currently lacks: `robots.txt`, `sitemap.xml`, a canonical `metadataBase`, Open Graph / Twitter card tags, and per-page canonical URLs.

**Architecture:** Everything lives in `web/` (Next.js 16 App Router on Vercel). We use Next's file conventions — `app/robots.ts` and `app/sitemap.ts` export default functions returning `MetadataRoute.Robots` / `MetadataRoute.Sitemap` objects, which Next serves as `/robots.txt` and `/sitemap.xml`. The site's canonical origin already exists as the `SITE_URL` env var (used by `app/feed.xml/route.ts` with a fail-loud `.invalid` fallback); we extract that logic into a shared `lib/site-url.ts` and reuse it everywhere so there is exactly one source of truth for the origin.

**Tech Stack:** Next.js 16.2.9 (App Router metadata file conventions), TypeScript, Vitest (`npm test` = `vitest run`), colocated `*.test.ts(x)` files.

## Global Constraints

- All work happens under `web/`; run all commands from `/Users/kaustubhkislay/aisafety-opportunities/web`.
- Branch off `origin/main` (current checkout is on `paper-controls` — do not build on it): `git fetch origin && git checkout -b feat/seo-foundations origin/main`.
- Canonical origin comes ONLY from `process.env.SITE_URL`. Fallback on missing env is `https://site-url-not-configured.invalid` plus a `console.error` — copy the existing behavior in `app/feed.xml/route.ts:12-17`, never a hardcoded plausible URL.
- The five indexable routes are exactly: `/`, `/theory-of-change`, `/partners`, `/privacy`, `/terms`. `/api/*` must be disallowed in robots.
- Do not change existing page `title` strings (they already carry the "— AI Safety Opportunities" suffix; adding a layout title template would double it).
- No new dependencies. No OG image asset in this plan (follow-up work; OG tags without an image still fix link previews' title/description/URL).
- Tests: vitest, colocated next to the file under test, `import { describe, it, expect } from "vitest"` style as in `app/legal-pages.test.tsx`.
- Merge policy: user has pre-approved self-merging green-CI PRs in this repo.

---

### Task 1: Shared `getSiteUrl()` helper

**Files:**
- Create: `web/lib/site-url.ts`
- Create: `web/lib/site-url.test.ts`
- Modify: `web/app/feed.xml/route.ts` (replace inline env logic with the helper)

**Interfaces:**
- Produces: `getSiteUrl(): string` — returns `process.env.SITE_URL` with any trailing slash stripped, or `"https://site-url-not-configured.invalid"` after `console.error`. Tasks 2–4 import it as `import { getSiteUrl } from "@/lib/site-url";`.

- [ ] **Step 1: Write the failing test**

```ts
// web/lib/site-url.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { getSiteUrl } from "@/lib/site-url";

describe("getSiteUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("returns SITE_URL when configured", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    expect(getSiteUrl()).toBe("https://aisopportunities.com");
  });

  it("strips a trailing slash", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com/");
    expect(getSiteUrl()).toBe("https://aisopportunities.com");
  });

  it("falls back to an obvious .invalid host and logs when unset", () => {
    vi.stubEnv("SITE_URL", "");
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(getSiteUrl()).toBe("https://site-url-not-configured.invalid");
    expect(err).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/site-url.test.ts`
Expected: FAIL — cannot resolve `@/lib/site-url`.

- [ ] **Step 3: Write minimal implementation**

```ts
// web/lib/site-url.ts
/**
 * Canonical site origin, from SITE_URL. Never ship a plausible-but-wrong
 * URL: a misconfigured deploy gets a reserved .invalid host so the mistake
 * is visible in the output itself.
 */
export function getSiteUrl(): string {
  const configured = process.env.SITE_URL;
  if (!configured) {
    console.error("site-url: SITE_URL is not configured");
    return "https://site-url-not-configured.invalid";
  }
  return configured.replace(/\/$/, "");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/site-url.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Refactor the feed route to use the helper**

In `web/app/feed.xml/route.ts`, add `import { getSiteUrl } from "@/lib/site-url";` and replace:

```ts
  let siteUrl = process.env.SITE_URL;
  if (!siteUrl) {
    // Never ship a plausible-but-wrong URL: use a reserved .invalid host so a
    // misconfigured deploy is obvious in the feed itself, and log it.
    console.error("feed.xml: SITE_URL is not configured");
    siteUrl = "https://site-url-not-configured.invalid";
  }
```

with:

```ts
  const siteUrl = getSiteUrl();
```

- [ ] **Step 6: Run the full web suite**

Run: `npm test`
Expected: PASS, including the existing `app/feed.xml/route.test.ts` (it asserts the same fallback behavior, now exercised through the helper). If a feed test spied on `console.error` message text containing "feed.xml:", update the assertion to the new "site-url:" prefix.

- [ ] **Step 7: Commit**

```bash
git add lib/site-url.ts lib/site-url.test.ts app/feed.xml/route.ts app/feed.xml/route.test.ts
git commit -m "refactor(web): extract getSiteUrl() as the single source of the canonical origin"
```

### Task 2: `app/robots.ts`

**Files:**
- Create: `web/app/robots.ts`
- Create: `web/app/robots.test.ts`

**Interfaces:**
- Consumes: `getSiteUrl(): string` from Task 1.
- Produces: `/robots.txt` route (Next file convention; default export returning `MetadataRoute.Robots`).

- [ ] **Step 1: Write the failing test**

```ts
// web/app/robots.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import robots from "@/app/robots";

describe("robots.txt", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("allows everything except /api/ and points at the sitemap", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    expect(robots()).toEqual({
      rules: { userAgent: "*", allow: "/", disallow: "/api/" },
      sitemap: "https://aisopportunities.com/sitemap.xml",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run app/robots.test.ts`
Expected: FAIL — cannot resolve `@/app/robots`.

- [ ] **Step 3: Write minimal implementation**

```ts
// web/app/robots.ts
import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site-url";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: "/api/" },
    sitemap: `${getSiteUrl()}/sitemap.xml`,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run app/robots.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/robots.ts app/robots.test.ts
git commit -m "feat(web): serve robots.txt (allow all, disallow /api/, sitemap link)"
```

### Task 3: `app/sitemap.ts`

**Files:**
- Create: `web/app/sitemap.ts`
- Create: `web/app/sitemap.test.ts`

**Interfaces:**
- Consumes: `getSiteUrl(): string` from Task 1.
- Produces: `/sitemap.xml` route listing the five indexable pages.

- [ ] **Step 1: Write the failing test**

```ts
// web/app/sitemap.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import sitemap from "@/app/sitemap";

describe("sitemap.xml", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("lists every indexable page as an absolute URL", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    const urls = sitemap().map((e) => e.url);
    expect(urls).toEqual([
      "https://aisopportunities.com",
      "https://aisopportunities.com/theory-of-change",
      "https://aisopportunities.com/partners",
      "https://aisopportunities.com/privacy",
      "https://aisopportunities.com/terms",
    ]);
  });

  it("marks the board itself as the highest-priority, most frequently changing page", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    const [home, ...rest] = sitemap();
    expect(home.priority).toBe(1);
    expect(home.changeFrequency).toBe("hourly");
    for (const entry of rest) {
      expect(entry.priority).toBeLessThan(1);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run app/sitemap.test.ts`
Expected: FAIL — cannot resolve `@/app/sitemap`.

- [ ] **Step 3: Write minimal implementation**

```ts
// web/app/sitemap.ts
import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site-url";

export default function sitemap(): MetadataRoute.Sitemap {
  const site = getSiteUrl();
  return [
    // The board is where opportunities appear and expire — the page crawlers
    // should revisit. The rest is near-static supporting copy.
    { url: site, changeFrequency: "hourly", priority: 1 },
    { url: `${site}/theory-of-change`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${site}/partners`, changeFrequency: "weekly", priority: 0.5 },
    { url: `${site}/privacy`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${site}/terms`, changeFrequency: "monthly", priority: 0.3 },
  ];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run app/sitemap.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/sitemap.ts app/sitemap.test.ts
git commit -m "feat(web): serve sitemap.xml listing the five indexable pages"
```

### Task 4: Root metadata — `metadataBase`, Open Graph, Twitter card, RSS alternate

**Files:**
- Modify: `web/app/layout.tsx:22-26` (the `metadata` export only)
- Create: `web/app/layout-metadata.test.ts`

**Interfaces:**
- Consumes: `getSiteUrl(): string` from Task 1.
- Produces: root `metadata` object all page metadata merges into; `metadataBase` makes every relative `alternates.canonical` (Task 5) and OG URL absolute.

- [ ] **Step 1: Write the failing test**

```ts
// web/app/layout-metadata.test.ts
// Asserts on the metadata export only — importing RootLayout itself would
// pull next/font, which vitest doesn't load.
import { describe, expect, it } from "vitest";
import { metadata } from "@/app/layout";

describe("root metadata", () => {
  it("sets metadataBase so relative canonicals and OG URLs become absolute", () => {
    expect(metadata.metadataBase).toBeInstanceOf(URL);
  });

  it("declares Open Graph and Twitter card tags", () => {
    expect(metadata.openGraph).toMatchObject({
      title: "AI Safety Opportunities",
      siteName: "AI Safety Opportunities",
      type: "website",
      url: "/",
    });
    expect(metadata.twitter).toMatchObject({ card: "summary" });
  });

  it("declares the canonical home URL and the RSS feed", () => {
    expect(metadata.alternates).toMatchObject({
      canonical: "/",
      types: { "application/rss+xml": "/feed.xml" },
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run app/layout-metadata.test.ts`
Expected: FAIL — `metadata.metadataBase` is undefined.

(If the import of `@/app/layout` itself fails on `next/font`, add `vi.mock("next/font/google", ...)` returning `{ Bricolage_Grotesque: () => ({ variable: "" }), Geist: () => ({ variable: "" }), Geist_Mono: () => ({ variable: "" }) }` at the top of the test — but try without first.)

- [ ] **Step 3: Write the implementation**

In `web/app/layout.tsx`, add the import and replace the `metadata` export:

```ts
import { getSiteUrl } from "@/lib/site-url";
```

```ts
const description =
  "A public, auto-updating board of AI-safety jobs, fellowships, grants, events, and courses.";

export const metadata: Metadata = {
  metadataBase: new URL(getSiteUrl()),
  title: "AI Safety Opportunities",
  description,
  alternates: {
    canonical: "/",
    types: { "application/rss+xml": "/feed.xml" },
  },
  openGraph: {
    title: "AI Safety Opportunities",
    description,
    siteName: "AI Safety Opportunities",
    type: "website",
    url: "/",
  },
  twitter: {
    card: "summary",
    title: "AI Safety Opportunities",
    description,
  },
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run app/layout-metadata.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Verify the build renders the tags**

Run: `npm run build 2>&1 | tail -5` — expected: build succeeds (metadataBase resolves via `SITE_URL` from `.env.local` if present, else logs the site-url error and uses the `.invalid` fallback; both are fine locally).

- [ ] **Step 6: Commit**

```bash
git add app/layout.tsx app/layout-metadata.test.ts
git commit -m "feat(web): metadataBase + Open Graph/Twitter tags + canonical and RSS alternates"
```

### Task 5: Per-page canonical URLs

**Files:**
- Modify: `web/app/theory-of-change/page.tsx` (metadata export, ~line 4)
- Modify: `web/app/partners/page.tsx` (metadata export, ~line 10)
- Modify: `web/app/privacy/page.tsx` (metadata export, ~line 4)
- Modify: `web/app/terms/page.tsx` (metadata export, ~line 4)
- Create: `web/app/page-canonicals.test.ts`

**Interfaces:**
- Consumes: `metadataBase` from Task 4 (turns these relative canonicals into absolute URLs at render time).

- [ ] **Step 1: Write the failing test**

```ts
// web/app/page-canonicals.test.ts
import { describe, expect, it } from "vitest";
import { metadata as toc } from "@/app/theory-of-change/page";
import { metadata as partners } from "@/app/partners/page";
import { metadata as privacy } from "@/app/privacy/page";
import { metadata as terms } from "@/app/terms/page";

describe("per-page canonical URLs", () => {
  it.each([
    ["/theory-of-change", toc],
    ["/partners", partners],
    ["/privacy", privacy],
    ["/terms", terms],
  ])("%s declares itself canonical", (path, metadata) => {
    expect(metadata.alternates?.canonical).toBe(path);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run app/page-canonicals.test.ts`
Expected: FAIL — 4 failures, `alternates` undefined on every page.

- [ ] **Step 3: Add the canonical to each page's metadata**

Add one line inside each existing `export const metadata: Metadata = { ... }` block — e.g. for `app/privacy/page.tsx`:

```ts
export const metadata: Metadata = {
  title: "Privacy — AI Safety Opportunities",
  description: "How this site collects, filters, and removes data.",
  alternates: { canonical: "/privacy" },
};
```

Same pattern for the other three, with canonicals `/terms`, `/theory-of-change`, `/partners` respectively (leave each page's existing `title`/`description` untouched).

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run app/page-canonicals.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full suite and commit**

Run: `npm test` — expected: everything green.

```bash
git add app/theory-of-change/page.tsx app/partners/page.tsx app/privacy/page.tsx app/terms/page.tsx app/page-canonicals.test.ts
git commit -m "feat(web): per-page canonical URLs"
```

### Task 6: Ship and verify in production

**Files:** none (PR + deploy verification).

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feat/seo-foundations
gh pr create --title "SEO foundations: robots.txt, sitemap.xml, canonical + OG metadata" --body "$(cat <<'EOF'
Adds the crawler/indexing surface the site was missing:

- `app/robots.ts` → /robots.txt (allow all, disallow /api/, sitemap link)
- `app/sitemap.ts` → /sitemap.xml (the five indexable pages)
- `metadataBase` + Open Graph/Twitter tags + RSS alternate in the root layout
- per-page canonical URLs
- `lib/site-url.ts` extracts the SITE_URL logic the feed route already used

No new deps. No OG image yet (follow-up). Origin comes only from SITE_URL,
with the same fail-loud `.invalid` fallback as feed.xml.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2 [ckpt — human]: Confirm `SITE_URL` is set in Vercel for Production**

`metadataBase`, robots, and sitemap all resolve from it at build time. It should already be there (feed.xml depends on it) — verify in the Vercel dashboard (or `vercel env ls`) before merging; if missing, add `SITE_URL=https://aisopportunities.com` and redeploy.

- [ ] **Step 3: Merge on green CI** (pre-approved for this repo), wait for the Vercel production deploy.

- [ ] **Step 4: Verify live**

```bash
curl -s https://aisopportunities.com/robots.txt
curl -s https://aisopportunities.com/sitemap.xml | head -20
curl -s https://aisopportunities.com | grep -o '<meta property="og:[^>]*>' | head
curl -s https://aisopportunities.com/privacy | grep -o '<link rel="canonical"[^>]*>'
```

Expected: robots.txt with the disallow + sitemap line; sitemap XML with five absolute `https://aisopportunities.com/...` URLs (no `.invalid` anywhere); `og:` meta tags on the home page; an absolute canonical link on /privacy.

- [ ] **Step 5 [ckpt — human]: Register the sitemap in Google Search Console**

Verify the `aisopportunities.com` property (DNS TXT via Squarespace, or the HTML-file method) and submit `https://aisopportunities.com/sitemap.xml`. Optional but recommended: Bing Webmaster Tools accepts the same sitemap.

## Out of scope (deliberate)

- **OG image** (`app/opengraph-image.png` or generated): needs a design pass; `twitter: { card: "summary" }` upgrades to `summary_large_image` when one lands.
- **`JobPosting` JSON-LD**: opportunities have no per-item URLs, and Google requires one canonical URL per posting — that's a per-opportunity-page feature, a much larger change.
- **Layout title template**: existing pages already suffix their titles manually; converting is churn with no SEO effect.
