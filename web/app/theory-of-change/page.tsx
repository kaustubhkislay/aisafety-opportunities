import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "ToC — AI Safety Opportunities",
  description: "Why this board exists and how it improves opportunity distribution in AI safety.",
};

function H({ children }: { children: React.ReactNode }) {
  return <h2 className="font-display mt-8 text-xl font-semibold">{children}</h2>;
}

function B({ children }: { children: React.ReactNode }) {
  return <li className="ml-5 list-disc leading-relaxed">{children}</li>;
}

export default function TheoryOfChangePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10 text-[15px]">
      <h1 className="font-display text-3xl font-bold text-[var(--brand)]">Theory of change</h1>

      <H>Why does this exist when 80k Hours and AISafety.com job boards exist?</H>
      <ul className="mt-2 space-y-1.5">
        <B>
          Job boards like these commonly lack opportunities that are shared only in AIS community
          discords/slacks.
        </B>
        <B>These opportunities should be distributed to as many capable candidates as possible.</B>
      </ul>

      <H>The distribution problem</H>
      <ul className="mt-2 space-y-1.5">
        <B>
          The distribution process though is very tedious. Usually, to be thorough, this involves
          joining every uni group discord/slack and sending each opportunity individually.
        </B>
        <B>This is a pain and isn&rsquo;t automated for ToS reasons.</B>
        <B>
          Our bot is the compliant version: owner-installed, using Discord&rsquo;s and
          Slack&rsquo;s official APIs, with read-only permissions and explicit consent per
          community.
        </B>
      </ul>

      <H>What we do</H>
      <ul className="mt-2 space-y-1.5">
        <B>Every opportunity posting is hosted and visible to prospective candidates.</B>
        <B>
          As quickly as possible: an opportunity is on the board about 20 seconds after it&rsquo;s
          posted.
        </B>
        <B>
          As digestibly as possible: one page with search, filters, and deadline grouping; a daily
          email digest of only what&rsquo;s new.
        </B>
      </ul>

      <H>Privacy and control</H>
      <ul className="mt-2 space-y-1.5">
        <B>
          Communities can keep opportunities private: tag a post <code>[private]</code> or{" "}
          <code>[uni-reserved]</code> and it is dropped inside your server — it is never
          transmitted and never enters our database.
        </B>
        <B>
          Changed your mind after posting? React 🔒 or edit a privacy tag in — the item is deleted
          from our database and disappears from the site within seconds.
        </B>
        <B>
          Removing the bot deletes everything your community ever contributed. Uninstall means
          gone.
        </B>
        <B>
          The entire pipeline is{" "}
          <a
            href="https://github.com/kaustubhkislay/aisafety-opportunities"
            className="text-[var(--brand-link)] transition-colors hover:text-[var(--brand-hover)]"
          >
            open source
          </a>
          .
        </B>
      </ul>

      <H>Guardrails</H>
      <ul className="mt-2 space-y-1.5">
        <B>
          Personal contact details (emails, phone numbers, &ldquo;DM me&rdquo;) are stripped
          before publishing.
        </B>
        <B>Link shorteners and suspicious domains are withheld rather than published.</B>
        <B>Anything can be pulled from the board instantly by the community that posted it.</B>
      </ul>

      <H>Why add your community</H>
      <ul className="mt-2 space-y-1.5">
        <B>A 1-minute install; nothing about how your community posts changes afterward.</B>
        <B>
          A low-cost way to improve the distribution of opportunities within the AI-safety
          community — your postings reach every capable candidate watching the board, and your
          members see everyone else&rsquo;s.
        </B>
      </ul>

      <footer className="mt-12 border-t border-[var(--edge)] pt-4 text-sm text-[var(--muted)]">
        <Link href="/" className="transition-colors hover:text-[var(--brand-hover)]">
          {"< Back to the board"}
        </Link>
      </footer>
    </main>
  );
}
