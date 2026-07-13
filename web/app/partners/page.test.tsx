import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PartnersPage from "@/app/partners/page";

describe("partners page pinned communities", () => {
  it("lists installed-but-silent communities even with no live records", async () => {
    // No Airtable env in tests -> loadOpportunitiesResult degrades to no items,
    // so anything rendered comes from the INSTALLED_PARTNERS pin list.
    render(await PartnersPage());
    expect(screen.getByText("Columbia AI Alignment Club (CAIAC)")).toBeInTheDocument();
    expect(screen.getByAltText(/Columbia AI Alignment Club .* logo/)).toBeInTheDocument();
    expect(screen.getByText("Yale AI Alignment (YAIA)")).toBeInTheDocument();
    expect(screen.getByText("AI Alignment @ Illinois")).toBeInTheDocument();
    expect(screen.queryByText(/no communities connected yet/i)).not.toBeInTheDocument();
  });
});
