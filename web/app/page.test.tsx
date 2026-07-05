import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("home page degraded state", () => {
  it("shows an unavailability notice when the data source is unreachable", async () => {
    // No Airtable env in tests -> loadOpportunitiesResult degrades.
    render(await Home());
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
  });
});
