import { describe, it, expect, afterEach, vi } from "vitest";
import { POST } from "@/app/api/feedback/route";

function req(body: unknown): Request {
  return new Request("http://localhost/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/feedback", () => {
  afterEach(() => {
    delete process.env.BACKEND_URL;
    vi.unstubAllGlobals();
  });

  it("400s on an empty message", async () => {
    expect((await POST(req({ message: "  " }))).status).toBe(400);
  });

  it("forwards a valid message to the backend", async () => {
    process.env.BACKEND_URL = "http://backend.test";
    const fakeFetch = vi.fn(async () => new Response(JSON.stringify({ stored: true }), { status: 200 }));
    vi.stubGlobal("fetch", fakeFetch);
    const res = await POST(req({ message: "great board", email: "" }));
    expect(res.status).toBe(200);
    expect(fakeFetch).toHaveBeenCalledWith(
      "http://backend.test/feedback",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
