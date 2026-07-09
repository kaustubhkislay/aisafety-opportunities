"use client";

import { useMemo, useState } from "react";
import type { Opportunity, OppType } from "@/lib/types";
import { filterAndSort } from "@/lib/filter";
import { deriveStatus, isFresh } from "@/lib/status";

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

function Pin({ urgent }: { urgent: boolean }) {
  const head = urgent ? "#d97706" : "var(--brand)";
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 32"
      className="absolute -top-3 left-1/2 h-7 w-5 -translate-x-1/2 drop-shadow-[0_1px_1px_rgba(28,25,23,0.35)]"
    >
      {/* needle */}
      <path d="M12 17 L12 30" stroke="#8a8378" strokeWidth="1.6" strokeLinecap="round" />
      {/* collar */}
      <rect x="9.2" y="14.5" width="5.6" height="3.4" rx="1" fill={head} opacity="0.85" />
      {/* head */}
      <circle cx="12" cy="9" r="6.5" fill={head} />
      {/* highlight */}
      <circle cx="9.6" cy="6.8" r="2" fill="#ffffff" opacity="0.4" />
    </svg>
  );
}

function Card({ o, now }: { o: Opportunity; now: Date }) {
  const chip = deadlineChip(o.deadline, now);
  const badge = TYPE_COLORS[o.type] ?? TYPE_COLORS.other;
  return (
    <li
      className="group relative flex flex-col gap-1.5 rounded-sm bg-[var(--card)] p-4 pt-6 shadow-[0_1px_4px_rgba(28,25,23,0.12)]"
    >
      <Pin urgent={chip.urgent} />
      <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.18em]">
        <span className="flex flex-wrap gap-2">
          <span className={`font-medium ${badge}`}>{o.type}</span>
          {o.categories.filter((c) => c !== "other").map((c) => (
            <span
              key={c}
              className={c === "tech" ? "font-medium text-teal-700" : "font-medium text-indigo-700"}
            >
              {c}
            </span>
          ))}
        </span>
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
        {[o.org, o.location, o.remote ? "remote" : null].filter(Boolean).join(" / ")}
      </p>
      {o.description && (
        <div
          role="tooltip"
          className="pointer-events-none invisible absolute left-2 right-2 top-[calc(100%-0.5rem)] z-20 max-h-56 overflow-hidden whitespace-pre-line rounded-sm bg-[var(--card)] p-3 text-[13px] leading-relaxed opacity-0 shadow-[0_4px_16px_rgba(28,25,23,0.25)] transition-opacity duration-150 group-hover:visible group-hover:opacity-100"
        >
          {o.description}
        </div>
      )}
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
      <ul className="grid grid-cols-2 gap-4 pt-1.5 sm:gap-5">
        {items.map((o) => (
          <Card key={o.dedupKey || `${o.title}-${o.link}`} o={o} now={now} />
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
  const [location, setLocation] = useState("");
  const [category, setCategory] = useState("");
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
        { text, types: type ? [type] : [], locations: location ? [location] : [], categories: category ? [category] : [], remoteOnly, showPast },
        now,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opportunities, text, type, location, category, remoteOnly, showPast, nowISO],
  );

  const groups = useMemo(() => {
    const fresh: Opportunity[] = [];
    const closing: Opportunity[] = [];
    const open: Opportunity[] = [];
    const past: Opportunity[] = [];
    for (const o of visible) {
      // Newly-added and closing-soon overlap: a fresh item with a near
      // deadline shows in both sections. Open holds whatever is in neither.
      const status = deriveStatus(o.deadline, now);
      if (status === "expired") {
        past.push(o);
        continue;
      }
      const isNew = isFresh(o.dateSeen, now);
      if (isNew) fresh.push(o);
      if (status === "closing-soon") closing.push(o);
      else if (!isNew) open.push(o);
    }
    return { fresh, closing, open, past };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, nowISO]);

  const control = "rounded bg-[var(--card)] px-3 py-1.5 text-sm shadow-[0_1px_3px_rgba(28,25,23,0.1)] focus:outline-none focus:ring-1 focus:ring-[var(--brand)] lg:w-full";

  return (
    <div className="lg:flex lg:items-start lg:gap-8">
      <div className="sticky top-0 z-10 -mx-4 mb-6 flex flex-wrap items-center gap-2 bg-[var(--board)]/95 px-4 py-3 backdrop-blur-sm lg:top-4 lg:order-2 lg:mx-0 lg:mt-12 lg:w-52 lg:shrink-0 lg:flex-col lg:items-stretch lg:rounded lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
        <input
          type="search"
          placeholder="Search the board…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className={`${control} w-full sm:w-auto sm:min-w-[10rem] sm:flex-1 lg:w-full`}
        />
        <select value={type} onChange={(e) => setType(e.target.value)} className={control} aria-label="Filter by type">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className={control}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          <option value="tech">tech</option>
          <option value="gov">gov</option>
          <option value="other">other</option>
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
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} />
          Show past
        </label>
      </div>

      <div className="lg:order-1 lg:min-w-0 lg:flex-1">
        <Section title="Newly added" items={groups.fresh} now={now} id="new" />
        <Section title="Closing this week" items={groups.closing} now={now} accent id="closing" />
        <Section title="Open" items={groups.open} now={now} id="open" />
        {showPast && <Section title="Past" items={groups.past} now={now} id="past" />}
        {visible.length === 0 && <p className="text-[var(--muted)]">Nothing on the board matches.</p>}
      </div>
    </div>
  );
}
