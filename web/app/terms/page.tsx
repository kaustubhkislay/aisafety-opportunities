import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms — AI Safety Opportunities",
  description: "Terms of use for this site.",
};

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <nav className="mb-6 text-sm text-gray-500">
        <Link href="/" className="transition-colors hover:text-[var(--brand-hover)]">
          {"< Back to the board"}
        </Link>
      </nav>
      <h1 className="text-2xl font-bold">Terms of Use</h1>
      <p className="mt-2 text-gray-600">Last updated 2026-07-05.</p>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">What this site is</h2>
        <p className="mt-2">
          AI Safety Opportunities is a free, open-source, automatically curated board of AI-safety
          jobs, fellowships, grants, events, and courses, aggregated from community Discord servers
          whose owners installed our bot.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">No warranty</h2>
        <p className="mt-2">
          Listings are extracted automatically and provided &quot;as is&quot;, without warranty of
          any kind. We do not verify, endorse, or guarantee any opportunity, organization, deadline,
          or link. Always verify details with the linked organization before applying or sharing
          personal information.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Acceptable use</h2>
        <p className="mt-2">
          Don&apos;t use the site or its feeds to spam, misrepresent listings, or attempt to inject
          malicious or misleading content into source communities. Server owners may remove the bot
          at any time, which deletes their data (see{" "}
          <Link href="/privacy" className="transition-colors hover:text-[var(--brand-hover)]">
            Privacy
          </Link>
          ).
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Changes</h2>
        <p className="mt-2">
          We may update these terms as the project evolves; the latest version always lives at this
          URL, with history in the open-source repository.
        </p>
      </section>

      <footer className="mt-12 text-sm text-gray-500">
        <Link href="/privacy" className="transition-colors hover:text-[var(--brand-hover)]">
          Privacy
        </Link>
      </footer>
    </main>
  );
}
