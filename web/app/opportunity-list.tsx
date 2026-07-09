"use client";

import { useMemo, useState } from "react";
import type { Opportunity, OppType } from "@/lib/types";
import { filterAndSort, splitLocations } from "@/lib/filter";
import { deriveStatus, isFresh } from "@/lib/status";

const TYPES: OppType[] = [
  "job", "internship", "fellowship", "grant", "event", "course", "reading-group", "other",
];

// Hollow uppercase tag pills, colored per type/category.
const PILL_COLORS: Record<string, string> = {
  job: "text-slate-600",
  internship: "text-sky-700",
  fellowship: "text-[var(--brand)]",
  grant: "text-green-700",
  event: "text-purple-700",
  course: "text-teal-700",
  "reading-group": "text-rose-700",
  tech: "text-teal-700",
  gov: "text-indigo-700",
  other: "text-stone-500",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function deadlineChip(
  deadline: string | null,
  now: Date,
): { text: string; urgent: boolean; dot: string } {
  if (!deadline) return { text: "rolling", urgent: false, dot: "bg-green-600" };
  const status = deriveStatus(deadline, now);
  if (status === "expired") return { text: "closed", urgent: false, dot: "bg-stone-400" };
  const due = new Date(`${deadline}T00:00:00Z`);
  if (status === "closing-soon") {
    const days = Math.round(
      (due.getTime() - Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())) / 86_400_000,
    );
    return {
      text: days <= 0 ? "closes today" : days === 1 ? "1 day left" : `${days} days left`,
      urgent: true,
      dot: "bg-red-600",
    };
  }
  return {
    text: `closes ${MONTHS[due.getUTCMonth()]} ${due.getUTCDate()}`,
    urgent: false,
    dot: "bg-sky-600",
  };
}

// Deterministic per-card look: paper style, fixture, and tilt are picked by
// hashing the dedup key, so the same card always renders the same way (no
// Math.random — SSR- and test-safe).
export function cardLook(key: string): { paper: number; fixture: number; tilt: number } {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return { paper: h % 6, fixture: (h >>> 3) % 3, tilt: (h >>> 5) % 4 };
}

const PAPERS = [
  "paper-graph",
  "paper-dotgrid",
  "paper-lined",
  "paper-torn",
  "paper-note",
  "paper-canvas",
];
const TILTS = ["tilt-1", "tilt-2", "tilt-3", "tilt-4"];

// Fixtures fastening each card to the board. Orange when the opportunity is
// closing soon, an unremarkable gray otherwise.
function Pin({ urgent }: { urgent: boolean }) {
  const head = urgent ? "#d97706" : "#9a9da3";
  return (
    <svg
      aria-hidden
      data-fixture="pin"
      data-urgent={urgent}
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

function Tape({ urgent }: { urgent: boolean }) {
  return (
    <div
      aria-hidden
      data-fixture="tape"
      data-urgent={urgent}
      className={`absolute -top-2.5 left-1/2 h-5 w-16 -translate-x-1/2 -rotate-3 shadow-[0_1px_2px_rgba(28,25,23,0.2)] ${
        urgent ? "bg-amber-500/55" : "bg-stone-300/65"
      }`}
    />
  );
}

function Clip({ urgent }: { urgent: boolean }) {
  const stroke = urgent ? "#d97706" : "#8a8d93";
  return (
    <svg
      aria-hidden
      data-fixture="clip"
      data-urgent={urgent}
      viewBox="0 0 20 44"
      className="absolute -top-4 left-7 h-10 w-5 drop-shadow-[0_1px_1px_rgba(28,25,23,0.3)]"
    >
      <path
        d="M6 12 a4 4 0 0 1 8 0 v22 a3 3 0 0 1 -6 0 V14 a1.5 1.5 0 0 1 3 0 v18"
        fill="none"
        stroke={stroke}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

const FIXTURES = [Pin, Tape, Clip];

function Card({ o, now }: { o: Opportunity; now: Date }) {
  const chip = deadlineChip(o.deadline, now);
  const [expanded, setExpanded] = useState(false);
  const look = cardLook(o.dedupKey || `${o.title}-${o.link}`);
  const Fixture = FIXTURES[look.fixture];
  const pill =
    "rounded border border-current px-1.5 py-0.5 text-[10px] font-medium uppercase leading-none tracking-[0.08em]";
  return (
    <li
      className={`relative flex flex-col gap-1.5 rounded-sm p-4 pt-6 ${PAPERS[look.paper]} ${TILTS[look.tilt]}`}
    >
      <Fixture urgent={chip.urgent} />
      <h3
        className={`font-display text-[17px] font-medium leading-snug ${
          expanded
            ? ""
            : "[display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] overflow-hidden"
        }`}
      >
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
      {expanded && o.description && (
        <p className="whitespace-pre-line text-[13px] leading-relaxed">{o.description}</p>
      )}
      <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
        <span className={`${pill} ${PILL_COLORS[o.type] ?? PILL_COLORS.other}`}>{o.type}</span>
        {o.categories.map((c) => (
          <span key={c} className={`${pill} ${PILL_COLORS[c] ?? PILL_COLORS.other}`}>
            {c}
          </span>
        ))}
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[12px]">
          <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full ${chip.dot}`} />
          <span className={chip.urgent ? "font-semibold text-amber-700" : "text-[var(--muted)]"}>
            {chip.text}
          </span>
        </span>
        {o.description && (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={expanded ? "Hide details" : "Show details"}
            onClick={() => setExpanded((e) => !e)}
            className="flex h-6 w-6 items-center justify-center rounded-full border border-stone-400/70 text-sm leading-none text-stone-600 transition-colors hover:border-stone-600 hover:text-stone-900"
          >
            {expanded ? "−" : "+"}
          </button>
        )}
      </div>
    </li>
  );
}

function MultiSelect({
  label,
  noun,
  options,
  selected,
  onChange,
  className,
}: {
  label: string;
  noun: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  className: string;
}) {
  const toggle = (opt: string) =>
    onChange(selected.includes(opt) ? selected.filter((s) => s !== opt) : [...selected, opt]);
  return (
    <details className="relative">
      <summary
        aria-label={label}
        className={`${className} block cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden`}
      >
        {selected.length === 0
          ? label
          : selected.length === 1
            ? selected[0]
            : `${selected.length} ${noun}`}
        {" ▾"}
      </summary>
      <div className="absolute left-0 z-20 mt-1 max-h-64 w-56 overflow-y-auto rounded-sm border border-stone-300/80 bg-[var(--card)] p-2 shadow-[0_4px_16px_rgba(28,25,23,0.25)]">
        {options.map((opt) => (
          <label key={opt} className="flex items-center gap-1.5 py-1 text-sm">
            <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} />
            <span className="min-w-0 break-words">{opt}</span>
          </label>
        ))}
      </div>
    </details>
  );
}

function Section({
  title,
  items,
  now,
  id,
}: {
  title: string;
  items: Opportunity[];
  now: Date;
  id?: string;
}) {
  if (items.length === 0) return null;
  return (
    <section className="mb-8 scroll-mt-20" id={id}>
      <h2 className="font-display mb-3 text-lg font-semibold">{title}</h2>
      <ul className="grid grid-cols-2 items-start gap-4 pt-1.5 sm:gap-5">
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
  const [types, setTypes] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [category, setCategory] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [showPast, setShowPast] = useState(false);

  const locationOptions = useMemo(
    () => Array.from(new Set(opportunities.flatMap((o) => splitLocations(o.location)))).sort(),
    [opportunities],
  );

  const visible = useMemo(
    () =>
      filterAndSort(
        opportunities,
        { text, types, locations, categories: category ? [category] : [], remoteOnly, showPast },
        now,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opportunities, text, types, locations, category, remoteOnly, showPast, nowISO],
  );

  const groups = useMemo(() => {
    const fresh: Opportunity[] = [];
    const open: Opportunity[] = [];
    const past: Opportunity[] = [];
    for (const o of visible) {
      // Closing-soon items stay in their section (deadline sort floats them
      // to the top of Open) and keep the urgent amber styling on the card.
      if (deriveStatus(o.deadline, now) === "expired") past.push(o);
      else if (isFresh(o.dateSeen, now)) fresh.push(o);
      else open.push(o);
    }
    return { fresh, open, past };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, nowISO]);

  // Controls dress like small paper scraps to match the card restyle:
  // white-adjacent, thin border, soft shadow, square-ish corners.
  const control = "rounded-sm border border-stone-300/80 bg-[var(--card)] px-3 py-1.5 text-sm shadow-[0_1px_3px_rgba(28,25,23,0.1)] focus:outline-none focus:ring-1 focus:ring-[var(--brand)] lg:w-full";
  // Native selects size to their longest <option> and never shrink, so one
  // long location value can force the page wider than a phone viewport.
  // The cap must be a fixed length: percentage max-widths are ignored
  // during intrinsic sizing, so max-w-full does not break the overflow.
  const select = `${control} max-w-56`;

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
        <MultiSelect
          label="All types"
          noun="types"
          options={TYPES}
          selected={types}
          onChange={setTypes}
          className={select}
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className={select}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          <option value="tech">tech</option>
          <option value="gov">gov</option>
          <option value="other">other</option>
        </select>
        {locationOptions.length > 0 && (
          <MultiSelect
            label="All locations"
            noun="locations"
            options={locationOptions}
            selected={locations}
            onChange={setLocations}
            className={select}
          />
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
        <Section title="Open" items={groups.open} now={now} id="open" />
        {showPast && <Section title="Past" items={groups.past} now={now} id="past" />}
        {visible.length === 0 && <p className="text-[var(--muted)]">Nothing on the board matches.</p>}
      </div>
    </div>
  );
}
