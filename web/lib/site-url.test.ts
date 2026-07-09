import { afterEach, describe, expect, it, vi } from "vitest";
import { getSiteUrl } from "@/lib/site-url";

describe("getSiteUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("returns SITE_URL when configured", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com");
    expect(getSiteUrl()).toBe("https://aisopportunities.com");
  });

  it("strips a trailing slash", () => {
    vi.stubEnv("SITE_URL", "https://aisopportunities.com/");
    expect(getSiteUrl()).toBe("https://aisopportunities.com");
  });

  it("falls back to an obvious .invalid host and logs when unset", () => {
    vi.stubEnv("SITE_URL", "");
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(getSiteUrl()).toBe("https://site-url-not-configured.invalid");
    expect(err).toHaveBeenCalledOnce();
  });
});
