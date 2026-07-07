import type { Metadata } from "next";
import Image from "next/image";
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

// Known community logos (files in web/public); communities without an entry
// render without a logo.
const LOGOS: Record<string, string> = {
  "Wisconsin AI Safety Initiative": "/waisi-full.png",
};

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
      <nav className="mb-6 text-sm text-[var(--muted)]">
        <Link href="/" className="hover:text-[var(--brand-hover)]">
          {"< Back to the board"}
        </Link>
      </nav>
      <h1 className="font-display text-3xl font-bold text-[var(--brand)]">Partner communities</h1>

      <ul className="mt-8 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        {partners.map(([name]) => (
          <li key={name} className="flex items-center gap-3">
            {LOGOS[name] && (
              <Image
                src={LOGOS[name]}
                alt={`${name} logo`}
                width={455}
                height={96}
                className="h-6 w-auto"
              />
            )}
            <span className="font-display text-lg font-medium">{name}</span>
          </li>
        ))}
        {partners.length === 0 && (
          <li className="col-span-full text-[var(--muted)]">No communities connected yet.</li>
        )}
      </ul>

      <section className="mt-12">
        <h2 className="font-display text-xl font-semibold">Add your community</h2>
        <p className="mt-2 text-sm">
          Run an AI-safety Discord? Install the bot in a minute — it reads only your
          opportunities channel, privacy tags are honored before anything leaves your server, and
          uninstalling deletes everything.
        </p>
        <a
          href={INSTALL_URL}
          className="mt-3 inline-block rounded bg-[var(--brand)] px-4 py-2 text-sm font-medium !text-white transition-colors hover:bg-[var(--brand-hover)] active:translate-y-px"
        >
          Install instructions
        </a>
      </section>
    </main>
  );
}
