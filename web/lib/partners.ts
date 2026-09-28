import { logoFor } from "@/lib/logos";

/**
 * Collapse per-server-name record counts into one entry per community,
 * sorted by count (descending). A community that renames its Discord guild /
 * Slack workspace keeps its old records under the old name, so two names can
 * refer to the same community; names that resolve to the same logo are merged
 * under the name with the most records.
 */
export function mergePartnerCounts(counts: Map<string, number>): [string, number][] {
  const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  const merged: [string, number][] = [];
  const byLogo = new Map<string, [string, number]>();
  for (const [name, count] of sorted) {
    const logo = logoFor(name);
    const existing = logo ? byLogo.get(logo) : undefined;
    if (existing) {
      existing[1] += count;
      continue;
    }
    const entry: [string, number] = [name, count];
    merged.push(entry);
    if (logo) byLogo.set(logo, entry);
  }
  return merged.sort((a, b) => b[1] - a[1]);
}
