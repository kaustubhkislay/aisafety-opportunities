import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { loadOpportunitiesResult } from "@/lib/airtable";
import { logoFor } from "@/lib/logos";
import { deriveStatus } from "@/lib/status";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Partner communities — AI Safety Opportunities",
  description: "The communities whose opportunities feed this board.",
};

const DISCORD_INSTALL_URL =
  "https://discord.com/oauth2/authorize?client_id=1523518596108652554&scope=bot&permissions=66560";
const SLACK_INSTALL_URL = "https://aisopportunities-backend.fly.dev/slack/install";
const INSTALL_DOCS_URL =
  "https://github.com/kaustubhkislay/aisafety-opportunities#install-the-bot-in-your-community-discord-or-slack";

// Community logos live in web/lib/logos.ts (alias-matched against the
// connected server/workspace name); communities without a match render
// without a logo.

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

      <ul className="mt-8 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        {partners.map(([name]) => {
          const logo = logoFor(name);
          return (
            <li key={name} className="flex items-center gap-3">
              {logo && (
                <Image
                  src={logo}
                  alt={`${name} logo`}
                  width={455}
                  height={96}
                  className="h-6 w-auto shrink-0"
                />
              )}
              <span className="min-w-0 font-display text-lg font-medium leading-snug">{name}</span>
            </li>
          );
        })}
        {partners.length === 0 && (
          <li className="col-span-full text-[var(--muted)]">No communities connected yet.</li>
        )}
      </ul>

      <section id="add" className="mt-12">
        <h2 className="font-display text-xl font-semibold">Add your community</h2>
        <p className="mt-2 text-sm">
          Run an AI-safety Discord or Slack? Install the bot in a minute — it reads only your
          opportunities channel, privacy tags are honored, and uninstalling deletes everything.
          On Slack, <code>/invite</code> the bot into the channel after installing.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href={DISCORD_INSTALL_URL}
            className="inline-block rounded bg-[var(--brand)] px-4 py-2 text-sm font-medium !text-white transition-colors hover:bg-[var(--brand-hover)] active:translate-y-px"
          >
            Add to Discord
          </a>
          <a
            href={SLACK_INSTALL_URL}
            className="inline-block rounded bg-[var(--brand)] px-4 py-2 text-sm font-medium !text-white transition-colors hover:bg-[var(--brand-hover)] active:translate-y-px"
          >
            Add to Slack
          </a>
        </div>
        <p className="mt-2 text-sm text-[var(--muted)]">
          <a href={INSTALL_DOCS_URL} className="hover:text-[var(--brand-hover)]">
            Full install instructions
          </a>
        </p>
      </section>
    </main>
  );
}
