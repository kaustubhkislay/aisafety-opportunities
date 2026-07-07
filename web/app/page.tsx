import Image from "next/image";
import { loadOpportunitiesResult } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";
import { SubscribeForm } from "@/app/subscribe-form";
import Link from "next/link";

export const revalidate = 3600;

const INSTALL_URL =
  "https://github.com/kaustubhkislay/aisafety-opportunities#install-the-bot-in-your-server-community-owners";

const FEEDBACK_FORM_URL =
  "https://docs.google.com/forms/d/1VNied9pCE5Fivrif-bMELj3ElNhY2HaCqN1VritakBE/viewform";

const toc =
  "text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] transition-colors hover:text-[var(--brand-hover)]";

export default async function Home() {
  const { items: opportunities, degraded } = await loadOpportunitiesResult();
  const now = new Date();

  return (
    <div className="mx-auto max-w-5xl px-2 py-5 sm:px-4 sm:py-8">
      <main className="board px-4 py-6 sm:px-6">
      <header className="mb-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-[var(--brand)] sm:text-3xl">
              AI Safety Opportunities
            </h1>
            <nav aria-label="Contents" className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
              <Link href="/partners" className={toc}>Partner communities</Link>
              <Link href="/theory-of-change" className={toc}>ToC</Link>
              <a href={FEEDBACK_FORM_URL} target="_blank" rel="noopener noreferrer" className={toc}>
                Feedback
              </a>
              <a href="/feed.xml" className={toc}>RSS</a>
            </nav>
          </div>
          <div className="flex flex-col items-start gap-2 lg:items-end">
            <SubscribeForm />
            <a
              href={INSTALL_URL}
              className="box-border w-44 rounded border border-[var(--brand)] px-3 py-1.5 text-center text-sm font-medium text-[var(--brand)] transition-colors hover:bg-[var(--brand-tint)] active:translate-y-px"
            >
              Add community
            </a>
          </div>
        </div>
      </header>

      {degraded && (
        <p className="mb-4 rounded border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Listings are temporarily unavailable — the data source could not be reached. Please
          check back soon.
        </p>
      )}
      <OpportunityList opportunities={opportunities} nowISO={now.toISOString()} />

      <footer className="mt-12 border-t border-[var(--edge)] pt-4 text-sm text-[var(--muted)]">
        <a href="https://waisi.org" target="_blank" rel="noopener noreferrer">
          <Image
            src="/waisi-full.png"
            alt="waisi"
            width={455}
            height={96}
            className="inline h-3.5 w-auto align-[-2px]"
          />
        </a>
        {" / "}
        <a href="/privacy" className="hover:text-[var(--brand-hover)]">Privacy</a>
        {" / "}
        <a href="/terms" className="hover:text-[var(--brand-hover)]">Terms</a>
        {" / "}
        <a href="https://github.com/kaustubhkislay/aisafety-opportunities" className="hover:text-[var(--brand-hover)]">
          Open source
        </a>
      </footer>
      </main>
    </div>
  );
}
