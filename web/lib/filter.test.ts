import { describe, it, expect } from "vitest";
import { filterAndSort } from "@/lib/filter";
import type { Opportunity } from "@/lib/types";

const NOW = new Date("2026-06-26T12:00:00Z");

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: null, link: null, location: null,
    remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "", sourceServers: [], categories: [], description: "",
    ...p,
  };
}

describe("filterAndSort", () => {
  it("text search matches title or org", () => {
    const items = [opp({ title: "Redwood Fellow" }), opp({ title: "Other", org: "Anthropic" })];
    expect(filterAndSort(items, { text: "redwood" }, NOW).map((o) => o.title)).toEqual(["Redwood Fellow"]);
    expect(filterAndSort(items, { text: "anthropic" }, NOW).map((o) => o.title)).toEqual(["Other"]);
  });
  it("type filter keeps only matching types", () => {
    const items = [opp({ title: "J", type: "job" }), opp({ title: "F", type: "fellowship" })];
    expect(filterAndSort(items, { types: ["fellowship"] }, NOW).map((o) => o.title)).toEqual(["F"]);
  });
  it("remoteOnly keeps only remote", () => {
    const items = [opp({ title: "R", remote: true }), opp({ title: "L", remote: false })];
    expect(filterAndSort(items, { remoteOnly: true }, NOW).map((o) => o.title)).toEqual(["R"]);
  });
  it("hides expired unless showPast", () => {
    const items = [opp({ title: "Old", deadline: "2026-01-01" }), opp({ title: "New", deadline: "2026-12-01" })];
    expect(filterAndSort(items, {}, NOW).map((o) => o.title)).toEqual(["New"]);
    expect(filterAndSort(items, { showPast: true }, NOW).map((o) => o.title).sort()).toEqual(["New", "Old"]);
  });
  it("sorts deadline asc, no-deadline last, dateSeen desc tiebreak", () => {
    const items = [
      opp({ title: "NoDeadlineA", deadline: null, dateSeen: "2026-06-01" }),
      opp({ title: "NoDeadlineB", deadline: null, dateSeen: "2026-06-20" }),
      opp({ title: "Soon", deadline: "2026-07-01" }),
      opp({ title: "Later", deadline: "2026-09-01" }),
    ];
    expect(filterAndSort(items, {}, NOW).map((o) => o.title)).toEqual(["Soon", "Later", "NoDeadlineB", "NoDeadlineA"]);
  });
});

describe("category searching across fields", () => {
  it("matches location, type, and community, not just title/org", () => {
    const items = [
      opp({ title: "A", location: "Berkeley, CA", dedupKey: "1" }),
      opp({ title: "B", type: "grant", dedupKey: "2" }),
      opp({ title: "C", sourceServers: ["WAISI"], dedupKey: "3" }),
    ];
    expect(filterAndSort(items, { text: "berkeley" }, NOW).map((o) => o.title)).toEqual(["A"]);
    expect(filterAndSort(items, { text: "grant" }, NOW).map((o) => o.title)).toEqual(["B"]);
    expect(filterAndSort(items, { text: "waisi" }, NOW).map((o) => o.title)).toEqual(["C"]);
  });

  it("filters by community", () => {
    const items = [
      opp({ title: "A", sourceServers: ["WAISI"], dedupKey: "1" }),
      opp({ title: "B", sourceServers: ["AI Safety Hub"], dedupKey: "2" }),
    ];
    const out = filterAndSort(items, { servers: ["WAISI"] }, NOW);
    expect(out.map((o) => o.title)).toEqual(["A"]);
  });
});

describe("sorters (per 80k / aisafety.com analysis)", () => {
  it("sorts newest-first by dateSeen when requested", () => {
    const items = [
      opp({ title: "Older", dateSeen: "2026-06-20", deadline: "2026-07-01", dedupKey: "1" }),
      opp({ title: "Newest", dateSeen: "2026-06-26", deadline: "2026-09-01", dedupKey: "2" }),
    ];
    expect(filterAndSort(items, { sortBy: "newest" }, NOW).map((o) => o.title)).toEqual([
      "Newest",
      "Older",
    ]);
  });

  it("filters by location", () => {
    const items = [
      opp({ title: "Bay", location: "Berkeley, CA", dedupKey: "1" }),
      opp({ title: "UK", location: "London", dedupKey: "2" }),
    ];
    expect(filterAndSort(items, { locations: ["London"] }, NOW).map((o) => o.title)).toEqual(["UK"]);
  });
});

describe("category filter", () => {
  it("matches any of an item's categories", () => {
    const items = [
      opp({ title: "Tech", categories: ["tech"], dedupKey: "1" }),
      opp({ title: "Both", categories: ["tech", "gov"], dedupKey: "2" }),
      opp({ title: "Other", categories: ["other"], dedupKey: "3" }),
    ];
    expect(filterAndSort(items, { categories: ["gov"] }, NOW).map((o) => o.title)).toEqual(["Both"]);
    expect(filterAndSort(items, { categories: ["tech"] }, NOW).map((o) => o.title).sort()).toEqual(["Both", "Tech"]);
  });
});
