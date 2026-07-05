import { describe, it, expect, afterEach, vi } from "vitest";
import { GET } from "@/app/feed.xml/route";

describe("GET /feed.xml", () => {
  afterEach(() => {
    delete process.env.SITE_URL;
    vi.restoreAllMocks();
  });

  it("serves RSS with the configured SITE_URL", async () => {
    process.env.SITE_URL = "https://opps.example";
    const res = await GET();
    expect(res.headers.get("Content-Type")).toContain("application/rss+xml");
    const xml = await res.text();
    expect(xml).toContain("<link>https://opps.example</link>");
    expect(xml).not.toContain("example.com");
  });

  it("logs an error and uses an .invalid placeholder when SITE_URL is unset", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const res = await GET();
    const xml = await res.text();
    expect(xml).not.toContain("https://example.com");
    expect(xml).toContain(".invalid");
    expect(spy).toHaveBeenCalledWith(expect.stringContaining("SITE_URL"));
  });
});
