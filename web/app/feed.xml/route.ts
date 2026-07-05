import { loadOpportunities } from "@/lib/airtable";
import { deriveStatus } from "@/lib/status";
import { toRss } from "@/lib/rss";

export const revalidate = 3600;

export async function GET(): Promise<Response> {
  const now = new Date();
  const items = (await loadOpportunities()).filter(
    (o) => deriveStatus(o.deadline, now) !== "expired",
  );
  let siteUrl = process.env.SITE_URL;
  if (!siteUrl) {
    // Never ship a plausible-but-wrong URL: use a reserved .invalid host so a
    // misconfigured deploy is obvious in the feed itself, and log it.
    console.error("feed.xml: SITE_URL is not configured");
    siteUrl = "https://site-url-not-configured.invalid";
  }
  return new Response(toRss(items, siteUrl), {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
