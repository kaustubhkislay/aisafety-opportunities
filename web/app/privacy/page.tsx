import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy — AI Safety Opportunities",
  description: "How this site collects, filters, and removes data.",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <nav className="mb-6 text-sm text-gray-500">
        <Link href="/" className="transition-colors hover:text-[var(--brand-hover)]">
          {"< Back to the board"}
        </Link>
      </nav>
      <h1 className="text-2xl font-bold">Privacy</h1>
      <p className="mt-2 text-gray-600">
        This whole project is open source, so everything described here is auditable in{" "}
        <a href="https://github.com/kaustubhkislay/aisafety-opportunities" className="transition-colors hover:text-[var(--brand-hover)]">
          the code
        </a>
        . Last updated 2026-07-05.
      </p>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">What we collect, and what never leaves your server</h2>
        <p className="mt-2">
          Our Discord bot reads only the channels a server owner explicitly authorizes. Before
          anything is transmitted, the bot runs an exclusion check <em>inside your server</em>:
          messages containing any of the tags <code>[private]</code>, <code>[uni-reserved]</code>,{" "}
          <code>school-specific</code>, <code>internal</code>, or <code>do-not-share</code>, and all messages in channels the
          owner marks private-by-default, are dropped on the spot and never sent to us.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Public by design — but only curated fields</h2>
        <p className="mt-2">
          Everything that survives filtering is published on this site; there is no private data
          product. An automated pipeline extracts structured opportunity fields (title,
          organization, type, deadline, link, location), strips personal contact details such as
          personal emails, phone numbers, and DM handles, and withholds suspicious links. The site
          shows only those curated fields — never the raw message text. The original message is
          retained in our processing store solely to support extraction and owner auditing, and is
          deleted by retraction or purge (below).
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Removing something</h2>
        <ul className="mt-2 list-disc pl-6 space-y-1">
          <li>
            <strong>Retraction:</strong> react to the original Discord message with the lock emoji
            (🔒), or edit it to add <code>[private]</code>, and the item is removed from the site.
          </li>
          <li>
            <strong>Uninstall purge:</strong> removing the bot from a server deletes all of that
            server&apos;s data from our stores — uninstall means gone.
          </li>
          <li>
            <strong>Owner visibility:</strong> server owners can audit exactly what has been
            ingested from their server at any time.
          </li>
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Email digest subscribers</h2>
        <p className="mt-2">
          If you subscribe to the email digest, we store your email address for the sole purpose of
          sending you the digest. We never share or sell it. Every digest includes an unsubscribe
          link; using it deactivates your subscription immediately.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Takedown and contact</h2>
        <p className="mt-2">
          To request removal of a listing or your data, use the retraction path above or email{" "}
          <a href="mailto:kaustubh.kislay@gmail.com" className="transition-colors hover:text-[var(--brand-hover)]">
            kaustubh.kislay@gmail.com
          </a>
          . Takedowns are handled fast.
        </p>
      </section>

      <footer className="mt-12 text-sm text-gray-500">
        <Link href="/terms" className="transition-colors hover:text-[var(--brand-hover)]">
          Terms
        </Link>
      </footer>
    </main>
  );
}
