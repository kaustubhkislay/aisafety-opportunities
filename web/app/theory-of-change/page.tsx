import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Theory of change — AI Safety Opportunities",
  description: "Why this board exists and how it helps people enter AI safety.",
};

export default function TheoryOfChangePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-3xl font-bold text-[var(--brand)]">Theory of change</h1>

      <section className="mt-8 space-y-4 text-[15px] leading-relaxed">
        <h2 className="font-display text-xl font-semibold">The problem</h2>
        <p>
          Most AI-safety opportunities — fellowships, research programs, grants, jobs, reading
          groups — are announced inside private community Discords and Slacks. Discovery is gated
          by your social graph: if you are not already in the right servers, you do not hear about
          the openings, and deadlines pass silently. The people this hurts most are exactly the
          people the field wants to attract — newcomers who are not yet plugged in.
        </p>

        <h2 className="font-display text-xl font-semibold">The intervention</h2>
        <p>
          Communities install a small open-source bot that reads only their opportunities channel.
          An automated pipeline filters chatter, strips personal information, extracts structured
          listings, merges duplicates across communities, and publishes everything to this public
          board within seconds — with a daily email digest of what is new.
        </p>

        <h2 className="font-display text-xl font-semibold">The mechanism</h2>
        <p>
          Aggregation turns many gated feeds into one open one. That lowers the cost of staying
          informed from &ldquo;be in ten servers and read them daily&rdquo; to &ldquo;check one
          page or read one email.&rdquo; More people see more opportunities earlier; applications
          go up; programs and orgs fill roles from a wider talent pool; and the field&rsquo;s
          on-ramps get used by people beyond the existing network.
        </p>

        <h2 className="font-display text-xl font-semibold">Why communities cooperate</h2>
        <p>
          Because the trust costs are engineered down: the code is fully open source, privacy tags
          are honored inside the community&rsquo;s own server before anything is transmitted,
          posting <code>[private]</code> or reacting 🔒 removes an item, and uninstalling the bot
          deletes everything that community contributed. Sharing opportunities is something
          communities already want — this makes it free.
        </p>

        <h2 className="font-display text-xl font-semibold">What we watch</h2>
        <p>
          Communities connected, opportunities live, how quickly new postings reach the board,
          digest subscribers, and click-throughs to applications. If the board grows those numbers
          without compromising a single privacy promise, the theory is working.
        </p>
      </section>

      <footer className="mt-12 border-t border-[var(--edge)] pt-4 text-sm text-[var(--muted)]">
        <Link href="/" className="hover:text-[var(--brand-hover)]">
          {"< Back to the board"}
        </Link>
      </footer>
    </main>
  );
}
