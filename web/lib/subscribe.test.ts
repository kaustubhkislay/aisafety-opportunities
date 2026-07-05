import { describe, it, expect } from "vitest";
import { isValidEmail, forwardSubscribe } from "@/lib/subscribe";

describe("isValidEmail", () => {
  it("accepts well-formed addresses", () => {
    expect(isValidEmail("a@b.com")).toBe(true);
    expect(isValidEmail("first.last+tag@sub.example.org")).toBe(true);
  });
  it("rejects malformed addresses", () => {
    for (const bad of ["", "nope", "a@b", "a b@c.com", "@b.com"]) {
      expect(isValidEmail(bad)).toBe(false);
    }
  });
});

describe("forwardSubscribe", () => {
  it("POSTs the email to the backend /subscribe and returns its result", async () => {
    const seen: Record<string, unknown> = {};
    const fakeFetch = (async (url: string, init: RequestInit) => {
      seen.url = url;
      seen.body = JSON.parse(init.body as string);
      return { ok: true, status: 200, json: async () => ({ subscribed: true, email: "a@x.com" }) };
    }) as unknown as typeof fetch;

    const result = await forwardSubscribe("a@x.com", "http://backend.local", fakeFetch);

    expect(seen.url).toBe("http://backend.local/subscribe");
    expect(seen.body).toEqual({ email: "a@x.com" });
    expect(result.ok).toBe(true);
    expect(result.data).toEqual({ subscribed: true, email: "a@x.com" });
  });

  it("surfaces a non-ok status without a body", async () => {
    const fakeFetch = (async () => ({ ok: false, status: 502, json: async () => ({}) })) as unknown as typeof fetch;
    const result = await forwardSubscribe("a@x.com", "http://backend.local", fakeFetch);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(502);
    expect(result.data).toBeUndefined();
  });
});
