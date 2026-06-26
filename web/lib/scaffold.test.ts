import { describe, it, expect } from "vitest";
import type { Opportunity } from "@/lib/types";

describe("scaffold", () => {
  it("Opportunity type is usable", () => {
    const o: Opportunity = {
      title: "t", org: "o", type: "job", deadline: null, link: null,
      location: null, remote: false, sourceServer: "s", sourceChannel: "c",
      dateSeen: null, dedupKey: "k",
    };
    expect(o.title).toBe("t");
  });
});
