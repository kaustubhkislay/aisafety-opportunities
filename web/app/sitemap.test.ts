import { afterEach, describe, expect, it, vi } from "vitest";
import sitemap from "@/app/sitemap";

describe("sitemap.xml", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("lists every indexable page as an absolute URL", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    const urls = sitemap().map((e) => e.url);
    expect(urls).toEqual([
      "https://aisopportunities.com",
      "https://aisopportunities.com/theory-of-change",
      "https://aisopportunities.com/partners",
      "https://aisopportunities.com/privacy",
      "https://aisopportunities.com/terms",
    ]);
  });

  it("marks the board itself as the highest-priority, most frequently changing page", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    const [home, ...rest] = sitemap();
    expect(home.priority).toBe(1);
    expect(home.changeFrequency).toBe("hourly");
    for (const entry of rest) {
      expect(entry.priority).toBeLessThan(1);
    }
  });
});
