import { describe, it, expect } from "vitest";
import { toRss } from "@/lib/rss";
import type { Opportunity } from "@/lib/types";

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: null, link: null, location: null,
    remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "", sourceServers: [], categories: [], description: "",
    ...p,
  };
}

describe("toRss", () => {
  it("empty list is still valid RSS", () => {
    const xml = toRss([], "https://site.example");
    expect(xml).toContain('<?xml version="1.0"');
    expect(xml).toContain('<rss version="2.0">');
    expect(xml).toContain("</rss>");
    expect(xml).not.toContain("<item>");
  });
  it("renders an item with link and guid", () => {
    const xml = toRss([opp({ title: "ML Fellow", org: "Redwood", link: "https://x.org/a", dedupKey: "url:x.org/a" })], "https://site.example");
    expect(xml).toContain("<item>");
    expect(xml).toContain("ML Fellow — Redwood");
    expect(xml).toContain("<link>https://x.org/a</link>");
    expect(xml).toContain('<guid isPermaLink="false">url:x.org/a</guid>');
  });
  it("escapes XML-special characters", () => {
    const xml = toRss([opp({ title: "A & B <C>", org: "O" })], "https://site.example");
    expect(xml).toContain("A &amp; B &lt;C&gt;");
    expect(xml).not.toContain("A & B <C>");
  });
});

describe("toRss hardening", () => {
  it("emits pubDate from dateSeen when present", () => {
    const xml = toRss([opp({ title: "X", dateSeen: "2026-06-25" })], "https://site.example");
    expect(xml).toContain("<pubDate>Thu, 25 Jun 2026 00:00:00 GMT</pubDate>");
  });
  it("omits pubDate when dateSeen is missing", () => {
    const xml = toRss([opp({ title: "X", dateSeen: null })], "https://site.example");
    expect(xml).not.toContain("<pubDate>");
  });
  it("escapes single quotes", () => {
    const xml = toRss([opp({ title: "O'Brien's role" })], "https://site.example");
    expect(xml).toContain("O&#39;Brien&#39;s role");
  });
});
