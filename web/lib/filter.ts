import type { Opportunity } from "@/lib/types";
import { deriveStatus } from "@/lib/status";

export interface Query {
  text?: string;
  types?: string[];
  servers?: string[];
  locations?: string[];
  categories?: string[];
  sortBy?: "deadline" | "newest";
  remoteOnly?: boolean;
  showPast?: boolean;
}

// A record's location can be a combined string like "London, UK + Washington,
// DC". Split it into atoms so the filter list has no overlapping entries and
// a multi-location record matches each of its cities individually.
export function splitLocations(location: string | null): string[] {
  if (!location) return [];
  return location
    .split("+")
    .map((l) => l.trim())
    .filter(Boolean);
}

export function filterAndSort(items: Opportunity[], query: Query, now: Date): Opportunity[] {
  const text = (query.text ?? "").trim().toLowerCase();
  const types = query.types ?? [];

  const servers = query.servers ?? [];

  const filtered = items.filter((o) => {
    const haystack = [o.title, o.org, o.location ?? "", o.type, ...(o.sourceServers ?? [])]
      .join(" ")
      .toLowerCase();
    if (text && !haystack.includes(text)) return false;
    if (types.length > 0 && !types.includes(o.type)) return false;
    if (servers.length > 0 && !(o.sourceServers ?? []).some((s) => servers.includes(s))) return false;
    if (
      (query.locations ?? []).length > 0 &&
      !splitLocations(o.location).some((l) => (query.locations ?? []).includes(l))
    )
      return false;
    if ((query.categories ?? []).length > 0 && !(o.categories ?? []).some((c) => (query.categories ?? []).includes(c))) return false;
    if (query.remoteOnly && !o.remote) return false;
    if (!query.showPast && deriveStatus(o.deadline, now) === "expired") return false;
    return true;
  });

  if (query.sortBy === "newest") {
    return filtered.sort((a, b) => {
      const da = a.dateSeen ?? "";
      const db = b.dateSeen ?? "";
      if (da !== db) return da > db ? -1 : 1;
      return (a.deadline ?? "9999") < (b.deadline ?? "9999") ? -1 : 1;
    });
  }

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
