import { loadOpportunitiesResult } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";
import Link from "next/link";

export const revalidate = 3600;

const INSTALL_URL =
  "https://github.com/kaustubhkislay/aisafety-opportunities#install-the-bot-in-your-server-community-owners";

// Anonymous Google Form; the Feedback link renders once this is set.
const FEEDBACK_FORM_URL = "";

const toc =
  "text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] transition-colors hover:text-[var(--brand-hover)]";

export default async function Home() {
  const { items: opportunities, degraded } = await loadOpportunitiesResult();
  const now = new Date();

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
      <header className="mb-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="font-display text-2xl font-bold text-[var(--brand)] sm:text-3xl">
            AI Safety Opportunities
          </h1>
          <a
            href={INSTALL_URL}
            className="w-fit rounded border-2 border-[var(--brand)] px-3 py-1.5 text-sm font-medium text-[var(--brand)] transition-colors hover:bg-[var(--brand-tint)] active:translate-y-px"
          >
            + Add your community
          </a>
        </div>
        <nav aria-label="Contents" className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          <Link href="/partners" className={toc}>Partner communities</Link>
          {FEEDBACK_FORM_URL && (
            <a href={FEEDBACK_FORM_URL} target="_blank" rel="noopener noreferrer" className={toc}>
              Feedback
            </a>
          )}
          <a href="/feed.xml" className={toc}>RSS</a>
        </nav>
      </header>

      {degraded && (
        <p className="mb-4 rounded border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Listings are temporarily unavailable — the data source could not be reached. Please
          check back soon.
        </p>
      )}
      <OpportunityList opportunities={opportunities} nowISO={now.toISOString()} />

      <footer className="mt-12 border-t border-[var(--edge)] pt-4 text-sm text-[var(--muted)]">
        <a href="/privacy" className="underline decoration-1 underline-offset-2 hover:text-[var(--brand-hover)]">Privacy</a>
        {" · "}
        <a href="/terms" className="underline decoration-1 underline-offset-2 hover:text-[var(--brand-hover)]">Terms</a>
        {" · "}
        <Link href="/partners" className="underline decoration-1 underline-offset-2 hover:text-[var(--brand-hover)]">Partners</Link>
        {" · "}
        <a href="https://github.com/kaustubhkislay/aisafety-opportunities" className="underline decoration-1 underline-offset-2 hover:text-[var(--brand-hover)]">
          Open source
        </a>
      </footer>
    </main>
  );
}
