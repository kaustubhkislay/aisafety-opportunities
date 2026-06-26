import { loadOpportunities } from "@/lib/airtable";
import { deriveStatus } from "@/lib/status";
import { toRss } from "@/lib/rss";

export const revalidate = 3600;

export async function GET(): Promise<Response> {
  const now = new Date();
  const items = (await loadOpportunities()).filter(
    (o) => deriveStatus(o.deadline, now) !== "expired",
  );
  const siteUrl = process.env.SITE_URL ?? "https://example.com";
  return new Response(toRss(items, siteUrl), {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
