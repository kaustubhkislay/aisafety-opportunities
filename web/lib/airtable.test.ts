import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mapRecord, fetchOpportunities, loadOpportunities, loadOpportunitiesResult } from "@/lib/airtable";

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

describe("loadOpportunities (build-safe wrapper)", () => {
  afterEach(() => {
    delete process.env.AIRTABLE_API_KEY;
    delete process.env.AIRTABLE_BASE_ID;
  });

  it("returns [] instead of throwing when env is not configured", async () => {
    delete process.env.AIRTABLE_API_KEY;
    delete process.env.AIRTABLE_BASE_ID;
    await expect(loadOpportunities()).resolves.toEqual([]);
  });

  it("returns [] when the fetch fails (e.g. non-ok / network error)", async () => {
    process.env.AIRTABLE_API_KEY = "key";
    process.env.AIRTABLE_BASE_ID = "appX";
    const fakeFetch = async () => ({ ok: false, status: 500, json: async () => ({}) }) as unknown as Response;
    await expect(loadOpportunities(fakeFetch as unknown as typeof fetch)).resolves.toEqual([]);
  });

  it("returns mapped records on success", async () => {
    process.env.AIRTABLE_API_KEY = "key";
    process.env.AIRTABLE_BASE_ID = "appX";
    const fakeFetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ records: [{ fields: { title: "A", org: "o", type: "job" } }] }),
    }) as unknown as Response;
    const result = await loadOpportunities(fakeFetch as unknown as typeof fetch);
    expect(result.map((r) => r.title)).toEqual(["A"]);
  });
});

describe("loadOpportunitiesResult (degraded-state flag)", () => {
  afterEach(() => {
    delete process.env.AIRTABLE_API_KEY;
    delete process.env.AIRTABLE_BASE_ID;
  });

  it("flags degraded (and returns []) when the fetch fails", async () => {
    process.env.AIRTABLE_API_KEY = "key";
    process.env.AIRTABLE_BASE_ID = "appX";
    const fakeFetch = async () => ({ ok: false, status: 500, json: async () => ({}) }) as unknown as Response;
    const result = await loadOpportunitiesResult(fakeFetch as unknown as typeof fetch);
    expect(result.items).toEqual([]);
    expect(result.degraded).toBe(true);
  });

  it("is not degraded on success", async () => {
    process.env.AIRTABLE_API_KEY = "key";
    process.env.AIRTABLE_BASE_ID = "appX";
    const fakeFetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ records: [{ fields: { title: "A" } }] }),
    }) as unknown as Response;
    const result = await loadOpportunitiesResult(fakeFetch as unknown as typeof fetch);
    expect(result.items.map((r) => r.title)).toEqual(["A"]);
    expect(result.degraded).toBe(false);
  });
});
