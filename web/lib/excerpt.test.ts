import { describe, it, expect } from "vitest";
import { sanitizeExcerpt } from "@/lib/excerpt";

describe("sanitizeExcerpt", () => {
  it("passes plain posting text through", () => {
    expect(sanitizeExcerpt("Apply to the ML fellowship by June 1.")).toBe(
      "Apply to the ML fellowship by June 1.",
    );
  });

  it("strips emails", () => {
    expect(sanitizeExcerpt("Questions? Email jane.doe+ai@uni.edu for info")).toBe(
      "Questions? Email [contact removed] for info",
    );
  });

  it("strips phone numbers", () => {
    expect(sanitizeExcerpt("Call +1 555-123-4567 to RSVP")).toBe(
      "Call [contact removed] to RSVP",
    );
  });

  it("keeps short numbers like years and dates", () => {
    expect(sanitizeExcerpt("Deadline June 1, 2026 at 5pm")).toBe(
      "Deadline June 1, 2026 at 5pm",
    );
  });

  it("strips discord mentions and channels, keeps emoji names", () => {
    expect(sanitizeExcerpt("Ping <@123456789> in <#987654> <:wave:11223344>")).toBe(
      "Ping in :wave:",
    );
  });

  it("unwraps slack links and mentions", () => {
    expect(
      sanitizeExcerpt("Apply: <https://example.org/apply|application form> via <@U0AB12CD3>"),
    ).toBe("Apply: application form via");
    expect(sanitizeExcerpt("See <https://example.org/jobs>")).toBe(
      "See https://example.org/jobs",
    );
    expect(sanitizeExcerpt("Post in <#C024BE7LR|opportunities>")).toBe(
      "Post in #opportunities",
    );
  });

  it("collapses blank-line runs and trims", () => {
    expect(sanitizeExcerpt("Line one\n\n\n\nLine two  \n")).toBe("Line one\n\nLine two");
  });

  it("truncates long text at a word boundary with ellipsis", () => {
    const long = "word ".repeat(200);
    const out = sanitizeExcerpt(long, 100);
    expect(out.length).toBeLessThanOrEqual(101);
    expect(out.endsWith("…")).toBe(true);
  });

  it("returns empty string for empty input", () => {
    expect(sanitizeExcerpt("")).toBe("");
  });
});
