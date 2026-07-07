"use client";

import { useMemo, useState } from "react";
import type { Opportunity, OppType } from "@/lib/types";
import { filterAndSort } from "@/lib/filter";
import { deriveStatus } from "@/lib/status";

const TYPES: OppType[] = [
  "job", "internship", "fellowship", "grant", "event", "course", "reading-group", "other",
];

const TYPE_COLORS: Record<string, string> = {
  job: "text-slate-600",
  internship: "text-sky-700",
  fellowship: "text-[var(--brand)]",
  grant: "text-green-700",
  event: "text-purple-700",
  course: "text-teal-700",
  "reading-group": "text-rose-700",
  other: "text-stone-500",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function deadlineChip(deadline: string | null, now: Date): { text: string; urgent: boolean } {
  if (!deadline) return { text: "no deadline", urgent: false };
  const status = deriveStatus(deadline, now);
  if (status === "expired") return { text: "closed", urgent: false };
  const due = new Date(`${deadline}T00:00:00Z`);
  if (status === "closing-soon") {
    const days = Math.round(
      (due.getTime() - Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())) / 86_400_000,
    );
    return {
      text: days <= 0 ? "closes today" : days === 1 ? "1 day left" : `${days} days left`,
      urgent: true,
    };
  }
  return { text: `closes ${MONTHS[due.getUTCMonth()]} ${due.getUTCDate()}`, urgent: false };
}

function Card({ o, now, index }: { o: Opportunity; now: Date; index: number }) {
  const chip = deadlineChip(o.deadline, now);
  const badge = TYPE_COLORS[o.type] ?? TYPE_COLORS.other;
  const tilt = index % 2 === 0 ? "-rotate-[0.4deg]" : "rotate-[0.4deg]";
  return (
    <li
      className={`relative flex flex-col gap-1.5 rounded-sm bg-[var(--card)] p-4 pt-5 shadow-[0_1px_4px_rgba(28,25,23,0.12)] transition-transform hover:rotate-0 ${tilt}`}
    >
      <span
        aria-hidden
        className={`absolute -top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rounded-full shadow-sm ${chip.urgent ? "bg-amber-500" : "bg-[var(--brand)]"}`}
      />
      <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.18em]">
        <span className={`font-medium ${badge}`}>{o.type}</span>
        <span className={chip.urgent ? "font-semibold text-amber-700" : "text-[var(--muted)]"}>
          {chip.text}
        </span>
      </div>
      <h3 className="font-display text-[17px] font-medium leading-snug [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] overflow-hidden">
        {o.link ? (
          <a
            href={o.link}
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-[var(--brand-hover)]"
          >
            {o.title}
          </a>
        ) : (
          o.title
        )}
      </h3>
      <p className="text-sm text-[var(--muted)]">
        {[o.org, o.location, o.remote ? "remote" : null].filter(Boolean).join(" · ")}
      </p>
    </li>
  );
}

function Section({
  title,
  items,
  now,
  accent,
  id,
}: {
  title: string;
  items: Opportunity[];
  now: Date;
  accent?: boolean;
  id?: string;
}) {
  if (items.length === 0) return null;
  return (
    <section className="mb-8 scroll-mt-20" id={id}>
      <h2 className={`font-display mb-3 text-lg font-semibold ${accent ? "text-amber-700" : ""}`}>
        {title}
      </h2>
      <ul className="grid grid-cols-1 gap-5 pt-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((o, i) => (
          <Card key={o.dedupKey || `${o.title}-${o.link}`} o={o} now={now} index={i} />
        ))}
      </ul>
    </section>
  );
}

export function OpportunityList({
  opportunities,
  nowISO,
}: {
  opportunities: Opportunity[];
  nowISO: string;
}) {
  const now = new Date(nowISO);
  const [text, setText] = useState("");
  const [type, setType] = useState("");
  const [sortBy, setSortBy] = useState<"deadline" | "newest">("deadline");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [showPast, setShowPast] = useState(false);

  const locations = useMemo(
    () => Array.from(new Set(opportunities.map((o) => o.location).filter((l): l is string => !!l))).sort(),
    [opportunities],
  );

  const visible = useMemo(
    () =>
      filterAndSort(
        opportunities,
        { text, types: type ? [type] : [], locations: location ? [location] : [], sortBy, remoteOnly, showPast },
        now,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opportunities, text, type, location, sortBy, remoteOnly, showPast, nowISO],
  );

  const groups = useMemo(() => {
    const today = nowISO.slice(0, 10);
    const fresh: Opportunity[] = [];
    const closing: Opportunity[] = [];
    const open: Opportunity[] = [];
    const past: Opportunity[] = [];
    for (const o of visible) {
      const status = deriveStatus(o.deadline, now);
      if (status !== "expired" && o.dateSeen === today) {
        fresh.push(o);
        continue;
      }
      if (status === "closing-soon") closing.push(o);
      else if (status === "expired") past.push(o);
      else open.push(o);
    }
    return { fresh, closing, open, past };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, nowISO]);

  const control = "rounded bg-[var(--card)] px-3 py-1.5 text-sm shadow-[0_1px_3px_rgba(28,25,23,0.1)] focus:outline-none focus:ring-1 focus:ring-[var(--brand)]";

  return (
    <div>
      <div className="sticky top-0 z-10 -mx-4 mb-6 flex flex-wrap items-center gap-2 bg-[var(--background)]/95 px-4 py-3 backdrop-blur-sm">
        <input
          type="search"
          placeholder="Search the board…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className={`${control} w-full sm:w-auto sm:min-w-[10rem] sm:flex-1`}
        />
        <select value={type} onChange={(e) => setType(e.target.value)} className={control} aria-label="Filter by type">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {locations.length > 0 && (
          <select
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className={control}
            aria-label="Filter by location"
          >
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        )}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as "deadline" | "newest")}
          className={control}
          aria-label="Sort by"
        >
          <option value="deadline">Closing soonest</option>
          <option value="newest">Newest first</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} />
          Show past
        </label>
      </div>

      <Section title="Newly added" items={groups.fresh} now={now} id="new" />
      <Section title="Closing this week" items={groups.closing} now={now} accent id="closing" />
      <Section title="Open" items={groups.open} now={now} id="open" />
      {showPast && <Section title="Past" items={groups.past} now={now} id="past" />}
      {visible.length === 0 && <p className="text-[var(--muted)]">Nothing on the board matches.</p>}
    </div>
  );
}
