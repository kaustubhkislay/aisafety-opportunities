import { describe, it, expect, beforeEach } from "vitest";
import { mapRecord, fetchOpportunities } from "@/lib/airtable";

describe("mapRecord", () => {
  it("maps Airtable fields to the typed model", () => {
    const o = mapRecord({
      title: "ML Fellow", org: "Redwood", type: "fellowship",
      deadline: "2026-08-01", link: "https://x.org/apply", location: "Remote",
      remote: true, source_server: "srv", source_channel: "jobs",
      date_seen: "2026-06-26", dedup_key: "url:x.org/apply",
    });
    expect(o.org).toBe("Redwood");
    expect(o.remote).toBe(true);
    expect(o.sourceServer).toBe("srv");
    expect(o.dateSeen).toBe("2026-06-26");
    expect(o.dedupKey).toBe("url:x.org/apply");
  });
  it("defaults missing fields (null for nullable, '' for required, false for remote)", () => {
    const o = mapRecord({ title: "t", org: "o", type: "job" });
    expect(o.deadline).toBeNull();
    expect(o.link).toBeNull();
    expect(o.location).toBeNull();
    expect(o.remote).toBe(false);
    expect(o.dedupKey).toBe("");
  });
});

describe("fetchOpportunities", () => {
  beforeEach(() => {
    process.env.AIRTABLE_API_KEY = "key";
    process.env.AIRTABLE_BASE_ID = "appX";
    process.env.AIRTABLE_TABLE_NAME = "Opportunities";
  });

  it("follows pagination and maps all records", async () => {
    const pages = [
      { records: [{ fields: { title: "A", org: "o", type: "job" } }], offset: "p2" },
      { records: [{ fields: { title: "B", org: "o", type: "job" } }] },
    ];
    let call = 0;
    const fakeFetch = async () => ({
      ok: true,
      status: 200,
      json: async () => pages[call++],
    }) as unknown as Response;

    const result = await fetchOpportunities(fakeFetch as unknown as typeof fetch);
    expect(result.map((r) => r.title)).toEqual(["A", "B"]);
  });

  it("throws on a non-ok response", async () => {
    const fakeFetch = async () => ({ ok: false, status: 429, json: async () => ({}) }) as unknown as Response;
    await expect(fetchOpportunities(fakeFetch as unknown as typeof fetch)).rejects.toThrow();
  });
});
