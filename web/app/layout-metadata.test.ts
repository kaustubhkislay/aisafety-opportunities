// web/app/layout-metadata.test.ts
// Asserts on the metadata export only — importing RootLayout itself would
// pull next/font, which vitest doesn't load.
import { describe, expect, it, vi } from "vitest";

vi.mock("next/font/google", () => ({
  Bricolage_Grotesque: () => ({ variable: "" }),
  Geist: () => ({ variable: "" }),
  Geist_Mono: () => ({ variable: "" }),
}));

import { metadata } from "@/app/layout";

describe("root metadata", () => {
  it("sets metadataBase so relative canonicals and OG URLs become absolute", () => {
    expect(metadata.metadataBase).toBeInstanceOf(URL);
  });

  it("declares Open Graph and Twitter card tags", () => {
    expect(metadata.openGraph).toMatchObject({
      title: "AI Safety Opportunities",
      siteName: "AI Safety Opportunities",
      type: "website",
      url: "/",
    });
    expect(metadata.twitter).toMatchObject({ card: "summary" });
  });

  it("declares the canonical home URL and the RSS feed", () => {
    expect(metadata.alternates).toMatchObject({
      canonical: "/",
      types: { "application/rss+xml": "/feed.xml" },
    });
  });
});
