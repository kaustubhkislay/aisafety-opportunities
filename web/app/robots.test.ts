import { afterEach, describe, expect, it, vi } from "vitest";
import robots from "@/app/robots";

describe("robots.txt", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("allows everything except /api/ and points at the sitemap", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    expect(robots()).toEqual({
      rules: { userAgent: "*", allow: "/", disallow: "/api/" },
      sitemap: "https://aisopportunities.com/sitemap.xml",
    });
  });
});
