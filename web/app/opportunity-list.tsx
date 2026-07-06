"use client";

import { useMemo, useState } from "react";
import type { Opportunity, OppType } from "@/lib/types";
import { filterAndSort } from "@/lib/filter";
import { deriveStatus } from "@/lib/status";

const TYPES: OppType[] = [
  "job", "internship", "fellowship", "grant", "event", "course", "reading-group", "other",
];

function deadlineLabel(deadline: string | null, now: Date): string {
  if (!deadline) return "no deadline";
  const status = deriveStatus(deadline, now);
  if (status === "expired") return "closed";
  return `closes ${deadline}`;
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

  return (
    <div>
      <div className="mb-6 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search title or org…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-w-[12rem] flex-1 rounded border px-3 py-2"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="rounded border px-3 py-2"
          aria-label="Filter by type"
        >
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {servers.length > 0 && (
          <select
            value={server}
            onChange={(e) => setServer(e.target.value)}
            className="rounded border px-3 py-2"
            aria-label="Filter by community"
          >
            <option value="">All communities</option>
            {servers.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} />
          Show past
        </label>
      </div>

      <ul className="space-y-4">
        {visible.map((o) => {
          const status = deriveStatus(o.deadline, now);
          return (
            <li
              key={o.dedupKey || `${o.title}-${o.link}`}
              className={`rounded border p-4 ${status === "expired" ? "opacity-50" : ""} ${status === "closing-soon" ? "border-amber-400" : ""}`}
            >
              <h2 className="font-semibold">
                {o.link ? (
                  <a href={o.link} target="_blank" rel="noopener noreferrer" className="underline">
                    {o.title}
                  </a>
                ) : (
                  o.title
                )}
              </h2>
              <p className="text-sm text-gray-600">
                {o.org} · {o.type}
                {o.location ? ` · ${o.location}` : ""}
                {o.remote ? " · remote" : ""}
              </p>
              <p className="text-sm">{deadlineLabel(o.deadline, now)}</p>
              {o.sourceServers.length > 0 && (
                <p className="text-xs text-gray-500">found in {o.sourceServers.join(", ")}</p>
              )}
            </li>
          );
        })}
      </ul>
      {visible.length === 0 && <p className="text-gray-500">No opportunities match.</p>}
    </div>
  );
}
