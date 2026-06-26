import { describe, it, expect } from "vitest";
import { filterAndSort } from "@/lib/filter";
import type { Opportunity } from "@/lib/types";

const NOW = new Date("2026-06-26T12:00:00Z");

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: null, link: null, location: null,
    remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "",
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
