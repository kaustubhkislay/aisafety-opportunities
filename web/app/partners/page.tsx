import type { Metadata } from "next";
import Link from "next/link";
import { loadOpportunitiesResult } from "@/lib/airtable";
import { deriveStatus } from "@/lib/status";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Partner communities — AI Safety Opportunities",
  description: "The communities whose opportunities feed this board.",
};

const INSTALL_URL =
  "https://github.com/kaustubhkislay/aisafety-opportunities#install-the-bot-in-your-server-community-owners";

export default async function PartnersPage() {
  const { items } = await loadOpportunitiesResult();
  const now = new Date();
  const counts = new Map<string, number>();
  for (const o of items) {
    if (deriveStatus(o.deadline, now) === "expired") continue;
    for (const s of o.sourceServers) counts.set(s, (counts.get(s) ?? 0) + 1);
  }
  const partners = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-3xl font-bold text-[var(--brand)]">Partner communities</h1>
      <p className="mt-2 text-[var(--muted)]">
        Every opportunity on the board is posted by a real community — these are the servers
        currently feeding it.
      </p>

      <ul className="mt-8 space-y-3">
        {partners.map(([name, count]) => (
          <li key={name} className="border-t border-[var(--edge)] pt-3">
            <span className="font-display text-lg font-medium">{name}</span>
            <span className="ml-2 text-sm text-[var(--muted)]">
              {count} open {count === 1 ? "opportunity" : "opportunities"}
            </span>
          </li>
        ))}
        {partners.length === 0 && (
          <li className="text-[var(--muted)]">No communities connected yet.</li>
        )}
      </ul>

      <section className="mt-10 border-t-2 border-[var(--brand)] pt-4">
        <h2 className="font-display text-xl font-semibold">Add your community</h2>
        <p className="mt-2 text-sm">
          Run an AI-safety Discord? Install the bot in two minutes — it reads only your
          opportunities channel, privacy tags are honored before anything leaves your server, and
          uninstalling deletes everything.
        </p>
        <a
          href={INSTALL_URL}
          className="mt-3 inline-block rounded bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--brand-hover)] active:translate-y-px"
        >
          {"Install instructions >"}
        </a>
      </section>

      <footer className="mt-12 border-t border-[var(--edge)] pt-4 text-sm text-[var(--muted)]">
        <Link href="/" className="hover:text-[var(--brand-hover)]">
          {"< Back to the board"}
        </Link>
      </footer>
    </main>
  );
}
