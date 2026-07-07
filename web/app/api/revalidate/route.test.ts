import { describe, it, expect, vi, beforeEach } from "vitest";

// vi.hoisted ensures the mock fn exists in the hoisted scope the factory runs in
const { revalidatePath } = vi.hoisted(() => ({ revalidatePath: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath }));

import { POST } from "@/app/api/revalidate/route";

describe("POST /api/revalidate", () => {
  beforeEach(() => {
    revalidatePath.mockClear();
    process.env.REVALIDATE_SECRET = "s3cret";
  });

  it("rejects a missing secret with 401", async () => {
    const res = await POST(new Request("https://site.example/api/revalidate", { method: "POST" }));
    expect(res.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
  it("rejects a wrong secret with 401", async () => {
    const res = await POST(new Request("https://site.example/api/revalidate?secret=wrong", { method: "POST" }));
    expect(res.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
  it("revalidates on a valid secret", async () => {
    const res = await POST(new Request("https://site.example/api/revalidate?secret=s3cret", { method: "POST" }));
    expect(res.status).toBe(200);
    expect(revalidatePath).toHaveBeenCalledWith("/");
    expect(revalidatePath).toHaveBeenCalledWith("/feed.xml");
    expect(revalidatePath).toHaveBeenCalledWith("/partners");
  });
});

describe("header-based secret", () => {
  it("accepts the secret via x-revalidate-secret header", async () => {
    process.env.REVALIDATE_SECRET = "sec";
    const res = await POST(
      new Request("http://localhost/api/revalidate", {
        method: "POST",
        headers: { "x-revalidate-secret": "sec" },
      }),
    );
    expect(res.status).toBe(200);
  });

  it("rejects a wrong header secret", async () => {
    process.env.REVALIDATE_SECRET = "sec";
    const res = await POST(
      new Request("http://localhost/api/revalidate", {
        method: "POST",
        headers: { "x-revalidate-secret": "wrong" },
      }),
    );
    expect(res.status).toBe(401);
  });
});
