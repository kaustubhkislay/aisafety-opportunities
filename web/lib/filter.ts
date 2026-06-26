import type { Opportunity } from "@/lib/types";
import { deriveStatus } from "@/lib/status";

export interface Query {
  text?: string;
  types?: string[];
  remoteOnly?: boolean;
  showPast?: boolean;
}

export function filterAndSort(items: Opportunity[], query: Query, now: Date): Opportunity[] {
  const text = (query.text ?? "").trim().toLowerCase();
  const types = query.types ?? [];

  const filtered = items.filter((o) => {
    if (text && !`${o.title} ${o.org}`.toLowerCase().includes(text)) return false;
    if (types.length > 0 && !types.includes(o.type)) return false;
    if (query.remoteOnly && !o.remote) return false;
    if (!query.showPast && deriveStatus(o.deadline, now) === "expired") return false;
    return true;
  });

  return filtered.sort((a, b) => {
    if (a.deadline && b.deadline) {
      if (a.deadline !== b.deadline) return a.deadline < b.deadline ? -1 : 1;
    } else if (a.deadline && !b.deadline) {
      return -1;
    } else if (!a.deadline && b.deadline) {
      return 1;
    }
    const as = a.dateSeen ?? "";
    const bs = b.dateSeen ?? "";
    return as > bs ? -1 : as < bs ? 1 : 0;
  });
}
