import { loadOpportunitiesResult } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";
import { FeedbackForm } from "@/app/feedback-form";
import Link from "next/link";

export const revalidate = 3600;

const INSTALL_URL =
  "https://github.com/kaustubhkislay/aisafety-opportunities#install-the-bot-in-your-server-community-owners";

const toc =
  "text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] transition-colors hover:text-[var(--brand-hover)]";

export default async function Home() {
  const { items: opportunities, degraded } = await loadOpportunitiesResult();
  const now = new Date();

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-3xl font-bold text-[var(--brand)]">
            AI Safety Opportunities
          </h1>
          <a
            href={INSTALL_URL}
            className="rounded border-2 border-[var(--brand)] px-3 py-1.5 text-sm font-medium text-[var(--brand)] transition-colors hover:bg-[var(--brand-tint)] active:translate-y-px"
          >
            + Add your community
          </a>
        </div>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Jobs, fellowships, grants, events, and courses — posted by AI-safety communities,
          curated automatically.
        </p>
        <nav aria-label="Contents" className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          <a href="#new" className={toc}>Newly added</a>
          <a href="#closing" className={toc}>Closing this week</a>
          <a href="#open" className={toc}>Open</a>
          <Link href="/partners" className={toc}>Partner communities</Link>
          <a href="#feedback" className={toc}>Feedback</a>
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

      <section id="feedback" className="mt-12 scroll-mt-20 border-t-2 border-[var(--brand)] pt-4">
        <h2 className="font-display mb-3 text-lg font-semibold">Feedback</h2>
        <FeedbackForm />
      </section>

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
