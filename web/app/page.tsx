import { loadOpportunitiesResult } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";
import { deriveStatus } from "@/lib/status";
import Link from "next/link";

export const revalidate = 3600;

const INSTALL_URL =
  "https://github.com/kaustubhkislay/aisafety-opportunities#install-the-bot-in-your-server-community-owners";

export default async function Home() {
  const { items: opportunities, degraded } = await loadOpportunitiesResult();
  const now = new Date();
  const open = opportunities.filter((o) => deriveStatus(o.deadline, now) !== "expired");
  const closingSoon = open.filter((o) => deriveStatus(o.deadline, now) === "closing-soon");
  const communities = new Set(opportunities.flatMap((o) => o.sourceServers));

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="font-display text-3xl font-bold text-[var(--brand)]">AI Safety Opportunities</h1>
          <p className="text-sm text-[var(--muted)]">
            {open.length} open · {closingSoon.length} closing soon
            {communities.size > 0 ? ` · ${communities.size} ${communities.size === 1 ? "community" : "communities"}` : ""}
          </p>
        </div>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Jobs, fellowships, grants, events, and courses — posted by AI-safety communities,
          curated automatically.{" "}
          <a href={INSTALL_URL} className="underline hover:text-[var(--brand)]">Add your community</a>
          {" · "}
          <a href="/feed.xml" className="underline hover:text-[var(--brand)]">RSS</a>
        </p>
      </header>

      {degraded && (
        <p className="mb-4 rounded border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Listings are temporarily unavailable — the data source could not be reached. Please
          check back soon.
        </p>
      )}
      <OpportunityList opportunities={opportunities} nowISO={now.toISOString()} />
      <footer className="mt-12 border-t border-[var(--edge)] pt-4 text-sm text-[var(--muted)]">
        <a href="/privacy" className="underline hover:text-[var(--brand)]">Privacy</a>
        {" · "}
        <a href="/terms" className="underline hover:text-[var(--brand)]">Terms</a>
        {" · "}
        <a href="https://github.com/kaustubhkislay/aisafety-opportunities" className="underline hover:text-[var(--brand)]">
          Open source
        </a>
      </footer>
    </main>
  );
}
