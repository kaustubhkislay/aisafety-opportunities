export type Status = "active" | "closing-soon" | "expired";

const DAY_MS = 24 * 60 * 60 * 1000;

function dayUTC(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

// "Newly added" window: first seen today or yesterday (UTC). A rolling ~48h
// window rather than "equals the render date", so the section doesn't empty
// at every UTC midnight (+ ISR staleness).
const FRESH_WINDOW_DAYS = 2;

export function isFresh(dateSeen: string | null, now: Date): boolean {
  if (!dateSeen) return false;
  const seen = new Date(`${dateSeen}T00:00:00Z`);
  if (Number.isNaN(seen.getTime())) return false;
  return (dayUTC(now) - dayUTC(seen)) / DAY_MS < FRESH_WINDOW_DAYS;
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
