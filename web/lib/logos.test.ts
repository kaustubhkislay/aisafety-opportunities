import { describe, it, expect } from "vitest";
import { logoFor } from "@/lib/logos";

describe("logoFor", () => {
  it("matches the exact directory name", () => {
    expect(logoFor("Stanford AI Alignment (SAIA)")).toBe("/logos/stanford-ai-alignment.webp");
  });

  it("matches the name without the parenthetical (typical guild name)", () => {
    expect(logoFor("Stanford AI Alignment")).toBe("/logos/stanford-ai-alignment.webp");
    expect(logoFor("Michigan AI Safety Initiative")).toBe(
      "/logos/michigan-ai-safety-initiative.webp",
    );
  });

  it("matches the acronym alone", () => {
    expect(logoFor("MAISI")).toBe("/logos/michigan-ai-safety-initiative.webp");
    expect(logoFor("CASI")).toBe("/logos/carnegie-mellon-ai-safety-initiative.webp");
  });

  it("is case- and punctuation-insensitive", () => {
    expect(logoFor("  stanford ai alignment ")).toBe("/logos/stanford-ai-alignment.webp");
    expect(logoFor("SafeAI@Penn Labs")).toBe(logoFor("safeai penn labs"));
  });

  it("keeps the first-party WAISI asset", () => {
    expect(logoFor("Wisconsin AI Safety Initiative")).toBe("/waisi-full.png");
    expect(logoFor("WAISI")).toBe("/waisi-full.png");
  });

  it("returns null for unknown communities", () => {
    expect(logoFor("Some Random Server")).toBeNull();
  });
});
