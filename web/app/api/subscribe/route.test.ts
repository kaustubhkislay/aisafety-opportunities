import { describe, it, expect, afterEach, vi } from "vitest";
import { POST } from "@/app/api/subscribe/route";

function req(body: unknown): Request {
  return new Request("http://localhost/api/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

describe("POST /api/subscribe", () => {
  afterEach(() => {
    delete process.env.BACKEND_URL;
    vi.unstubAllGlobals();
  });

  it("400s on malformed JSON", async () => {
    const res = await POST(req("{nope"));
    expect(res.status).toBe(400);
  });

  it("400s on an invalid email", async () => {
    const res = await POST(req({ email: "not-an-email" }));
    expect(res.status).toBe(400);
  });

  it("500s when BACKEND_URL is not configured", async () => {
    const res = await POST(req({ email: "a@b.co" }));
    expect(res.status).toBe(500);
  });

  it("forwards a valid email to the backend and returns its response", async () => {
    process.env.BACKEND_URL = "http://backend.test";
    const fakeFetch = vi.fn(async () =>
      new Response(JSON.stringify({ status: "subscribed" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fakeFetch);
    const res = await POST(req({ email: "a@b.co" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "subscribed" });
    expect(fakeFetch).toHaveBeenCalledWith(
      "http://backend.test/subscribe",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
