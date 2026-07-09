import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site-url";

export default function sitemap(): MetadataRoute.Sitemap {
  const site = getSiteUrl();
  return [
    // The board is where opportunities appear and expire — the page crawlers
    // should revisit. The rest is near-static supporting copy.
    { url: site, changeFrequency: "hourly", priority: 1 },
    { url: `${site}/theory-of-change`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${site}/partners`, changeFrequency: "weekly", priority: 0.5 },
    { url: `${site}/privacy`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${site}/terms`, changeFrequency: "monthly", priority: 0.3 },
  ];
}
