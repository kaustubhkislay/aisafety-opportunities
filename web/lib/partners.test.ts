import { describe, it, expect } from "vitest";
import { mergePartnerCounts } from "@/lib/partners";

describe("mergePartnerCounts", () => {
  it("merges names that resolve to the same community logo", () => {
    const counts = new Map([
      ["PAIA", 5],
      ["PAIA (Princeton AI Alignment)", 4],
      ["Wisconsin AI Safety Initiative", 3],
    ]);
    expect(mergePartnerCounts(counts)).toEqual([
      ["PAIA", 9],
      ["Wisconsin AI Safety Initiative", 3],
    ]);
  });

  it("keeps communities without a logo separate", () => {
    const counts = new Map([
      ["Some Community", 2],
      ["Another Community", 1],
    ]);
    expect(mergePartnerCounts(counts)).toEqual([
      ["Some Community", 2],
      ["Another Community", 1],
    ]);
  });
});
