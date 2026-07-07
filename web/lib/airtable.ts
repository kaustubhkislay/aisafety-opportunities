import { sanitizeExcerpt } from "@/lib/excerpt";
import type { Opportunity } from "@/lib/types";

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}
function strOrNull(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

export function mapRecord(fields: Record<string, unknown>): Opportunity {
  return {
    title: str(fields.title),
    org: str(fields.org),
    type: str(fields.type) || "other",
    deadline: strOrNull(fields.deadline),
    link: strOrNull(fields.link),
    location: strOrNull(fields.location),
    remote: Boolean(fields.remote),
    sourceServer: str(fields.source_server),
    sourceChannel: str(fields.source_channel),
    dateSeen: strOrNull(fields.date_seen),
    dedupKey: str(fields.dedup_key),
    categories: Array.isArray(fields.categories)
      ? fields.categories.filter((c): c is string => typeof c === "string")
      : [],
    sourceServers: str(fields.source_servers)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    // Sanitize server-side: only the scrubbed excerpt ever reaches the client.
    description: sanitizeExcerpt(str(fields.raw_text)),
  };
}

interface AirtablePage {
  records: { fields: Record<string, unknown> }[];
  offset?: string;
}

export async function fetchOpportunities(
  fetchImpl: typeof fetch = fetch,
): Promise<Opportunity[]> {
  const key = process.env.AIRTABLE_API_KEY;
  const base = process.env.AIRTABLE_BASE_ID;
  const table = process.env.AIRTABLE_TABLE_NAME ?? "Opportunities";
  if (!key || !base) throw new Error("Airtable env not configured");

  const out: Opportunity[] = [];
  let offset: string | undefined;
  do {
    const url = new URL(`https://api.airtable.com/v0/${base}/${encodeURIComponent(table)}`);
    url.searchParams.set("pageSize", "100");
    if (offset) url.searchParams.set("offset", offset);
    const res = await fetchImpl(url.toString(), {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (!res.ok) throw new Error(`Airtable request failed: ${res.status}`);
    const data = (await res.json()) as AirtablePage;
    for (const rec of data.records) out.push(mapRecord(rec.fields));
    offset = data.offset;
  } while (offset);
  return out;
}

// Build-safe wrapper: the site is statically prerendered (ISR), so the page and
// feed render at build time when Airtable env/connectivity may be absent (e.g.
// CI). Per the design spec, a fetch failure must degrade to an empty list (and
// log) rather than crash the build — ISR then serves the last good page once
// data is reachable.
export async function loadOpportunitiesResult(
  fetchImpl: typeof fetch = fetch,
): Promise<{ items: Opportunity[]; degraded: boolean }> {
  try {
    return { items: await fetchOpportunities(fetchImpl), degraded: false };
  } catch (err) {
    console.error("loadOpportunities: falling back to empty list:", err);
    return { items: [], degraded: true };
  }
}

export async function loadOpportunities(
  fetchImpl: typeof fetch = fetch,
): Promise<Opportunity[]> {
  return (await loadOpportunitiesResult(fetchImpl)).items;
}
