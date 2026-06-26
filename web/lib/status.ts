export type Status = "active" | "closing-soon" | "expired";

const DAY_MS = 24 * 60 * 60 * 1000;

function dayUTC(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

export function deriveStatus(deadline: string | null, now: Date): Status {
  if (!deadline) return "active";
  const parsed = new Date(deadline);
  if (Number.isNaN(parsed.getTime())) return "active";
  const days = (dayUTC(parsed) - dayUTC(now)) / DAY_MS;
  if (days < 0) return "expired";
  if (days <= 7) return "closing-soon";
  return "active";
}
