import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OpportunityList, cardLook } from "@/app/opportunity-list";
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
  it("filters by location via checkboxes and supports multiple selections", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Bay Role", location: "Berkeley, CA", dedupKey: "a" }),
          opp({ title: "UK Role", location: "London", dedupKey: "b" }),
          opp({ title: "NYC Role", location: "New York", dedupKey: "c" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "London" }));
    expect(screen.getByText("UK Role")).toBeInTheDocument();
    expect(screen.queryByText("Bay Role")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: "New York" }));
    expect(screen.getByText("UK Role")).toBeInTheDocument();
    expect(screen.getByText("NYC Role")).toBeInTheDocument();
    expect(screen.queryByText("Bay Role")).not.toBeInTheDocument();
  });

  it("splits combined locations so the option list has no overlapping entries", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "UK Only", location: "London, UK", dedupKey: "a" }),
          opp({ title: "UK And DC", location: "London, UK + Washington, DC", dedupKey: "b" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    // one "London, UK" option (not a separate combined entry), plus the atom "Washington, DC"
    expect(screen.getAllByRole("checkbox", { name: "London, UK" })).toHaveLength(1);
    expect(screen.getByRole("checkbox", { name: "Washington, DC" })).toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "London, UK + Washington, DC" }),
    ).not.toBeInTheDocument();

    // the combined record matches either of its atoms
    await userEvent.click(screen.getByRole("checkbox", { name: "Washington, DC" }));
    expect(screen.getByText("UK And DC")).toBeInTheDocument();
    expect(screen.queryByText("UK Only")).not.toBeInTheDocument();
  });

  it("filters by type via checkboxes with multiple selections", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "A Job", type: "job", dedupKey: "a" }),
          opp({ title: "A Grant", type: "grant", dedupKey: "b" }),
          opp({ title: "An Event", type: "event", dedupKey: "c" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "job" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "grant" }));
    expect(screen.getByText("A Job")).toBeInTheDocument();
    expect(screen.getByText("A Grant")).toBeInTheDocument();
    expect(screen.queryByText("An Event")).not.toBeInTheDocument();
  });
});

describe("board grouping", () => {
  it("puts closing-soon items in Open (no separate section) with the urgent chip", () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Urgent", deadline: "2026-06-28", dedupKey: "u" }),
          opp({ title: "Relaxed", deadline: "2026-09-01", dedupKey: "r" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.queryByRole("heading", { name: /closing this week/i })).not.toBeInTheDocument();
    const open = screen.getByRole("heading", { name: /^open$/i }).closest("section")!;
    expect(within(open).getByText("Urgent")).toBeInTheDocument();
    expect(within(open).getByText("Relaxed")).toBeInTheDocument();
    // deadline-soon styling survives: relative chip in amber
    expect(within(open).getByText(/2 days left/)).toHaveClass("text-amber-700");
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

describe("filter controls", () => {
  it("caps select width so a long location option cannot widen the page on mobile", () => {
    render(
      <OpportunityList
        opportunities={[
          opp({
            title: "Long Loc",
            location: "Remote (potential coworking in London, Tel Aviv, SF, tentatively DC)",
            dedupKey: "ll",
          }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    // Fixed-length cap required: percentage max-widths are ignored during
    // intrinsic sizing, so max-w-full would not prevent the overflow.
    expect(screen.getByLabelText("All locations")).toHaveClass("max-w-56");
    expect(screen.getByLabelText("All types")).toHaveClass("max-w-56");
    expect(screen.getByLabelText("All categories")).toHaveClass("max-w-56");
  });
});

describe("category badges and filter", () => {
  it("renders full-word hollow pills for type and categories", () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "X", type: "fellowship", categories: ["tech", "gov"], dedupKey: "x" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    const card = screen.getAllByRole("listitem").find((li) => within(li).queryByText("X"))!;
    expect(within(card).getByText("fellowship")).toHaveClass("border", "uppercase");
    expect(within(card).getByText("tech")).toHaveClass("border", "text-teal-700");
    expect(within(card).getByText("gov")).toHaveClass("border", "text-indigo-700");
  });

  it("filters by category via checkboxes with multiple selections", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Techy", categories: ["tech"], dedupKey: "a" }),
          opp({ title: "Policy", categories: ["gov"], dedupKey: "b" }),
          opp({ title: "Misc", categories: ["other"], dedupKey: "c" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    // "gov"/"other" also exist in the types popover, so scope to categories
    const catPopover = screen.getByLabelText("All categories").closest("details")!;
    await userEvent.click(within(catPopover).getByRole("checkbox", { name: "gov" }));
    expect(screen.getByText("Policy")).toBeInTheDocument();
    expect(screen.queryByText("Techy")).not.toBeInTheDocument();
    expect(screen.queryByText("Misc")).not.toBeInTheDocument();

    await userEvent.click(within(catPopover).getByRole("checkbox", { name: "other" }));
    expect(screen.getByText("Policy")).toBeInTheDocument();
    expect(screen.getByText("Misc")).toBeInTheDocument();
    expect(screen.queryByText("Techy")).not.toBeInTheDocument();
  });
});

describe("group overlap", () => {
  it("a fresh closing-soon item sits in Newly added, keeping the urgent styling", () => {
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
    expect(within(fresh).getByText("Urgent Fresh")).toBeInTheDocument();
    expect(within(fresh).getByText(/2 days left/)).toHaveClass("text-amber-700");
    expect(screen.getAllByText("Urgent Fresh")).toHaveLength(1);
  });
});

describe("bulletin card restyle", () => {
  it("expands and collapses the description with the +/− button", async () => {
    render(
      <OpportunityList
        opportunities={[
          opp({ title: "Expandable", description: "Deep dive details here.", dedupKey: "e" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.queryByText("Deep dive details here.")).not.toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: "Show details" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(screen.getByText("Deep dive details here.")).toBeInTheDocument();

    const close = screen.getByRole("button", { name: "Hide details" });
    expect(close).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(close);
    expect(screen.queryByText("Deep dive details here.")).not.toBeInTheDocument();
  });

  it("omits the toggle when there is no description", () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "Bare", description: "", dedupKey: "b" })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });

  it("assigns a deterministic paper style, fixture, and tilt per dedup key", () => {
    const a = cardLook("some-key");
    expect(cardLook("some-key")).toEqual(a);
    expect(a.paper).toBeGreaterThanOrEqual(0);
    expect(a.paper).toBeLessThan(6);
    expect(a.fixture).toBeLessThan(3);
    expect(a.tilt).toBeLessThan(4);
    // different keys spread across looks
    const papers = new Set(["a", "b2", "c33", "d444", "e5555", "f6", "g77", "h888"].map((k) => cardLook(k).paper));
    expect(papers.size).toBeGreaterThan(2);
  });

  it("marks the fixture urgent only when closing soon", () => {
    const { container } = render(
      <OpportunityList
        opportunities={[
          opp({ title: "Urgent", deadline: "2026-06-28", dedupKey: "u" }),
          opp({ title: "Chill", deadline: "2026-09-01", dedupKey: "c" }),
        ]}
        nowISO={NOW_ISO}
      />,
    );
    const fixtures = Array.from(container.querySelectorAll("[data-fixture]"));
    expect(fixtures).toHaveLength(2);
    const urgentFlags = fixtures.map((f) => f.getAttribute("data-urgent")).sort();
    expect(urgentFlags).toEqual(["false", "true"]);
  });

  it("shows a rolling status for deadline-less opportunities", () => {
    render(
      <OpportunityList
        opportunities={[opp({ title: "Open Ended", deadline: null, dedupKey: "r" })]}
        nowISO={NOW_ISO}
      />,
    );
    expect(screen.getByText("rolling")).toBeInTheDocument();
  });
});
