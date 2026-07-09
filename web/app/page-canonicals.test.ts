import { describe, expect, it } from "vitest";
import { metadata as toc } from "@/app/theory-of-change/page";
import { metadata as partners } from "@/app/partners/page";
import { metadata as privacy } from "@/app/privacy/page";
import { metadata as terms } from "@/app/terms/page";

describe("per-page canonical URLs", () => {
  it.each([
    ["/theory-of-change", toc],
    ["/partners", partners],
    ["/privacy", privacy],
    ["/terms", terms],
  ])("%s declares itself canonical", (path, metadata) => {
    expect(metadata.alternates?.canonical).toBe(path);
  });
});
