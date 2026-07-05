import type { Opportunity } from "@/lib/types";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function pubDate(dateSeen: string | null): string {
  if (!dateSeen) return "";
  const d = new Date(dateSeen);
  if (Number.isNaN(d.getTime())) return "";
  return `<pubDate>${d.toUTCString()}</pubDate>`;
}

export function toRss(items: Opportunity[], siteUrl: string): string {
  const entries = items
    .map((o) => {
      const link = o.link ?? siteUrl;
      const title = esc(o.org ? `${o.title} — ${o.org}` : o.title);
      const desc = esc(
        [o.type, o.location, o.deadline ? `deadline ${o.deadline}` : null]
          .filter(Boolean)
          .join(" · "),
      );
      const guid = esc(o.dedupKey || link);
      return `    <item><title>${title}</title><link>${esc(link)}</link><guid isPermaLink="false">${guid}</guid>${pubDate(o.dateSeen)}<description>${desc}</description></item>`;
    })
    .join("\n");

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0"><channel>',
    "<title>AI Safety Opportunities</title>",
    `<link>${esc(siteUrl)}</link>`,
    "<description>Opportunities in AI safety</description>",
    entries,
    "</channel></rss>",
  ].join("\n");
}
