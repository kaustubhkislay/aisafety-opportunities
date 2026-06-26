import { describe, it, expect } from "vitest";
import { deriveStatus } from "@/lib/status";

const NOW = new Date("2026-06-26T12:00:00Z");

describe("deriveStatus", () => {
  it("no deadline is active", () => {
    expect(deriveStatus(null, NOW)).toBe("active");
  });
  it("past deadline is expired", () => {
    expect(deriveStatus("2026-06-25", NOW)).toBe("expired");
  });
  it("today is closing-soon", () => {
    expect(deriveStatus("2026-06-26", NOW)).toBe("closing-soon");
  });
  it("within 7 days is closing-soon", () => {
    expect(deriveStatus("2026-07-03", NOW)).toBe("closing-soon");
  });
  it("more than 7 days out is active", () => {
    expect(deriveStatus("2026-08-01", NOW)).toBe("active");
  });
  it("invalid deadline is active", () => {
    expect(deriveStatus("not-a-date", NOW)).toBe("active");
  });
});
