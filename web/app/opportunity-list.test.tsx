import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OpportunityList } from "@/app/opportunity-list";
import type { Opportunity } from "@/lib/types";

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: "2027-01-01", link: "https://x.org",
    location: null, remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "", sourceServers: [], sourceServers: [],
    ...p,
  };
}

const NOW_ISO = "2026-06-26T12:00:00Z";

describe("OpportunityList", () => {
  it("renders opportunities and filters by search text", async () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "Redwood Fellow", dedupKey: "a" }), opp({ title: "Anthropic SWE", dedupKey: "b" })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByText("Redwood Fellow")).toBeInTheDocument();
    expect(screen.getByText("Anthropic SWE")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox"), "redwood");
    expect(screen.getByText("Redwood Fellow")).toBeInTheDocument();
    expect(screen.queryByText("Anthropic SWE")).not.toBeInTheDocument();
  });

  it("links the title out to the application URL", () => {
    render(<OpportunityList opportunities={[opp({ title: "ML Fellow", link: "https://apply.example/x" })]} nowISO={NOW_ISO} />);
    const link = screen.getByRole("link", { name: /ML Fellow/ });
    expect(link).toHaveAttribute("href", "https://apply.example/x");
    expect(link).toHaveAttribute("target", "_blank");
  });
});

describe("server attribution", () => {
  it("shows which communities an opportunity was found in", () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "ML Fellow", sourceServers: ["AI Safety Hub", "WAISI"] })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByText(/found in AI Safety Hub, WAISI/)).toBeInTheDocument();
  });
  it("omits attribution when no community is recorded", () => {
    render(<OpportunityList opportunities={[opp({ title: "X" })]} nowISO={NOW_ISO} />);
    expect(screen.queryByText(/found in/)).not.toBeInTheDocument();
  });
});

describe("community filter", () => {
  it("offers the communities present and filters by selection", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "From WAISI", sourceServers: ["WAISI"], dedupKey: "a" }),
          opp({ title: "From Hub", sourceServers: ["AI Safety Hub"], dedupKey: "b" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Filter by community"), "WAISI");
    expect(screen.getByText("From WAISI")).toBeInTheDocument();
    expect(screen.queryByText("From Hub")).not.toBeInTheDocument();
  });
});
