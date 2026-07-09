import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OpportunityList } from "@/app/opportunity-list";
import type { Opportunity } from "@/lib/types";

function opp(p: Partial<Opportunity>): Opportunity {
  return {
    title: "T", org: "O", type: "job", deadline: "2027-01-01", link: "https://x.org",
    location: null, remote: false, sourceServer: "", sourceChannel: "", dateSeen: null, dedupKey: "", sourceServers: [], categories: [], description: "",
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
  it("does not show found-in stamps on cards (moved to /partners)", () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "ML Fellow", sourceServers: ["AI Safety Hub"] })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.queryByText(/found in/)).not.toBeInTheDocument();
  });
});

describe("location filter and sort", () => {
  it("filters by location", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Bay Role", location: "Berkeley, CA", dedupKey: "a" }),
          opp({ title: "UK Role", location: "London", dedupKey: "b" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Filter by location"), "London");
    expect(screen.getByText("UK Role")).toBeInTheDocument();
    expect(screen.queryByText("Bay Role")).not.toBeInTheDocument();
  });

});

describe("board grouping", () => {
  it("groups cards under Closing this week and Open headings", () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Urgent", deadline: "2026-06-28", dedupKey: "u" }),
          opp({ title: "Relaxed", deadline: "2026-09-01", dedupKey: "r" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByRole("heading", { name: /closing this week/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^open$/i })).toBeInTheDocument();
  });

  it("shows a Past section only when showPast is on", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Gone", deadline: "2026-01-01", dedupKey: "g" }),
          opp({ title: "Live", deadline: "2026-09-01", dedupKey: "l" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.queryByRole("heading", { name: /past/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/show past/i));
    expect(screen.getByRole("heading", { name: /past/i })).toBeInTheDocument();
    expect(screen.getByText("Gone")).toBeInTheDocument();
  });

  it("renders a relative chip for imminent deadlines", () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "Soon", deadline: "2026-06-29", dedupKey: "s" })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByText(/3 days left/)).toBeInTheDocument();
  });
});

describe("newly added", () => {
  it("shows a Newly added section for items first seen today, without duplicating them below", () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Fresh Today", deadline: "2026-09-01", dateSeen: "2026-06-26", dedupKey: "f" }),
          opp({ title: "Older", deadline: "2026-09-01", dateSeen: "2026-06-20", dedupKey: "o" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByRole("heading", { name: /newly added/i })).toBeInTheDocument();
    expect(screen.getAllByText("Fresh Today")).toHaveLength(1);
    expect(screen.getByText("Older")).toBeInTheDocument();
  });

  it("keeps yesterday's items in Newly added (survives the UTC-midnight rollover)", () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Fresh Yesterday", deadline: "2026-09-01", dateSeen: "2026-06-25", dedupKey: "y" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    const fresh = screen.getByRole("heading", { name: /newly added/i }).closest("section")!;
    expect(within(fresh).getByText("Fresh Yesterday")).toBeInTheDocument();
  });
});

describe("category badges and filter", () => {
  it("renders category badges on cards", () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "X", categories: ["tech", "gov"], dedupKey: "x" })]}
        nowISO={NOW_ISO}
      />,
    );
    // dropdown options also carry the labels, so scope to the card
    const card = screen.getByRole("listitem");
    expect(within(card).getByText("tech")).toBeInTheDocument();
    expect(within(card).getByText("gov")).toBeInTheDocument();
  });

  it("filters by category", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Techy", categories: ["tech"], dedupKey: "a" }),
          opp({ title: "Policy", categories: ["gov"], dedupKey: "b" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Filter by category"), "gov");
    expect(screen.getByText("Policy")).toBeInTheDocument();
    expect(screen.queryByText("Techy")).not.toBeInTheDocument();
  });
});

describe("group overlap", () => {
  it("an item that is both fresh and closing-soon shows in both sections", () => {
    render(
      <OpportunityList
        opportunities={[
          // first seen today AND closing within the week
          opp({ title: "Urgent Fresh", deadline: "2026-06-28", dateSeen: "2026-06-26", dedupKey: "uf" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    const fresh = screen.getByRole("heading", { name: /newly added/i }).closest("section")!;
    const closing = screen.getByRole("heading", { name: /closing this week/i }).closest("section")!;
    expect(within(fresh).getByText("Urgent Fresh")).toBeInTheDocument();
    expect(within(closing).getByText("Urgent Fresh")).toBeInTheDocument();
    // and it doesn't leak into Open as well
    expect(screen.queryByRole("heading", { name: /^open$/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("Urgent Fresh")).toHaveLength(2);
  });
});
