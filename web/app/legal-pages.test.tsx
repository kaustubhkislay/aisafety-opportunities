import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PrivacyPage from "@/app/privacy/page";
import TermsPage from "@/app/terms/page";
import Home from "@/app/page";

describe("privacy page", () => {
  it("renders the privacy policy heading", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1, name: /privacy/i })).toBeInTheDocument();
  });

  it("documents the edge-exclusion tag vocabulary", () => {
    render(<PrivacyPage />);
    const body = document.body.textContent ?? "";
    for (const tag of ["[private]", "[uni-reserved]", "school-specific", "internal", "do-not-share"]) {
      expect(body).toContain(tag);
    }
  });

  it("documents retraction, uninstall purge, and owner visibility", () => {
    render(<PrivacyPage />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/lock/i);
    expect(body).toMatch(/purge|deleted/i);
    expect(body).toMatch(/owner/i);
  });

  it("states that only curated fields are shown, never raw message text", () => {
    render(<PrivacyPage />);
    expect(document.body.textContent).toMatch(/raw message text|raw_text/i);
  });

  it("covers subscriber emails and unsubscribe", () => {
    render(<PrivacyPage />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/unsubscribe/i);
    expect(body).toMatch(/email/i);
  });

  it("provides a takedown contact", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("link", { name: /kaustubh\.kislay@gmail\.com/i })).toBeInTheDocument();
  });
});

describe("terms page", () => {
  it("renders the terms heading", () => {
    render(<TermsPage />);
    expect(screen.getByRole("heading", { level: 1, name: /terms/i })).toBeInTheDocument();
  });

  it("notes that listings are provided as-is without warranty", () => {
    render(<TermsPage />);
    expect(document.body.textContent).toMatch(/as is|without warranty/i);
  });
});

describe("home footer", () => {
  it("links to the privacy and terms pages", async () => {
    render(await Home());
    expect(screen.getByRole("link", { name: /privacy/i })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: /terms/i })).toHaveAttribute("href", "/terms");
  });
});
