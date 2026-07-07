"use client";

import { useMemo, useState } from "react";
import type { Opportunity, OppType } from "@/lib/types";
import { filterAndSort } from "@/lib/filter";
import { deriveStatus } from "@/lib/status";
import { SubscribeForm } from "@/app/subscribe-form";

const TYPES: OppType[] = [
  "job", "internship", "fellowship", "grant", "event", "course", "reading-group", "other",
];

const TYPE_COLORS: Record<string, string> = {
  job: "bg-slate-100 text-slate-700",
  internship: "bg-sky-100 text-sky-800",
  fellowship: "bg-amber-100 text-amber-800",
  grant: "bg-green-100 text-green-800",
  event: "bg-purple-100 text-purple-800",
  course: "bg-teal-100 text-teal-800",
  "reading-group": "bg-rose-100 text-rose-800",
  other: "bg-stone-100 text-stone-600",
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

function Card({ o, now }: { o: Opportunity; now: Date }) {
  const chip = deadlineChip(o.deadline, now);
  const badge = TYPE_COLORS[o.type] ?? TYPE_COLORS.other;
  return (
    <li
      className={`flex flex-col gap-2 rounded-lg bg-[var(--card)] p-4 shadow-sm ${chip.urgent ? "border-t-2 border-amber-500" : ""}`}
    >
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className={`rounded-full px-2 py-0.5 font-medium ${badge}`}>{o.type}</span>
        <span className={chip.urgent ? "font-semibold text-amber-700" : "text-[var(--muted)]"}>
          {chip.text}
        </span>
      </div>
      <h3 className="font-display text-base font-semibold leading-snug [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] overflow-hidden">
        {o.link ? (
          <a href={o.link} target="_blank" rel="noopener noreferrer" className="hover:text-amber-700">
            {o.title}
          </a>
        ) : (
          o.title
        )}
      </h3>
      <p className="text-sm text-[var(--muted)]">
        {[o.org, o.location, o.remote ? "remote" : null].filter(Boolean).join(" · ")}
      </p>
      {o.sourceServers.length > 0 && (
        <p className="mt-auto w-fit border border-dotted border-[var(--muted)] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-[var(--muted)]">
          found in {o.sourceServers.join(", ")}
        </p>
      )}
    </li>
  );
}

function Section({
  title,
  items,
  now,
  accent,
}: {
  title: string;
  items: Opportunity[];
  now: Date;
  accent?: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <section className="mb-8">
      <h2 className={`font-display mb-3 text-lg font-semibold ${accent ? "text-amber-700" : ""}`}>
        {title} <span className="text-sm font-normal text-[var(--muted)]">({items.length})</span>
      </h2>
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
  const [server, setServer] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [showPast, setShowPast] = useState(false);
  const [subscribeOpen, setSubscribeOpen] = useState(false);

  const servers = useMemo(
    () => Array.from(new Set(opportunities.flatMap((o) => o.sourceServers))).sort(),
    [opportunities],
  );

  const visible = useMemo(
    () =>
      filterAndSort(
        opportunities,
        { text, types: type ? [type] : [], servers: server ? [server] : [], remoteOnly, showPast },
        now,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opportunities, text, type, server, remoteOnly, showPast, nowISO],
  );

  const groups = useMemo(() => {
    const closing: Opportunity[] = [];
    const open: Opportunity[] = [];
    const past: Opportunity[] = [];
    for (const o of visible) {
      const status = deriveStatus(o.deadline, now);
      if (status === "closing-soon") closing.push(o);
      else if (status === "expired") past.push(o);
      else open.push(o);
    }
    return { closing, open, past };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, nowISO]);

  const pill = "rounded-full border border-[var(--edge)] bg-[var(--card)] px-3 py-1.5 text-sm";

  return (
    <div>
      <div className="sticky top-0 z-10 -mx-4 mb-6 flex flex-wrap items-center gap-2 bg-[var(--background)]/95 px-4 py-3 backdrop-blur-sm">
        <input
          type="search"
          placeholder="Search the board…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className={`${pill} min-w-[10rem] flex-1`}
        />
        <select value={type} onChange={(e) => setType(e.target.value)} className={pill} aria-label="Filter by type">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {servers.length > 0 && (
          <select
            value={server}
            onChange={(e) => setServer(e.target.value)}
            className={pill}
            aria-label="Filter by community"
          >
            <option value="">All communities</option>
            {servers.map((s) => (
              <option key={s} value={s}>{s}</option>
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
        <button
          type="button"
          onClick={() => setSubscribeOpen((v) => !v)}
          className={`${pill} ml-auto font-medium text-amber-700 hover:bg-amber-50`}
        >
          ✉ Daily digest
        </button>
      </div>

      {subscribeOpen && (
        <div className="mb-6">
          <SubscribeForm />
        </div>
      )}

      <Section title="Closing this week" items={groups.closing} now={now} accent />
      <Section title="Open" items={groups.open} now={now} />
      {showPast && <Section title="Past" items={groups.past} now={now} />}
      {visible.length === 0 && <p className="text-[var(--muted)]">Nothing on the board matches.</p>}
    </div>
  );
}
