import { revalidatePath } from "next/cache";

export async function POST(req: Request): Promise<Response> {
  // Header preferred (query strings leak into logs); query kept for manual use.
  const secret =
    req.headers.get("x-revalidate-secret") ?? new URL(req.url).searchParams.get("secret");
  const expected = process.env.REVALIDATE_SECRET;
  if (!expected || secret !== expected) {
    return new Response("unauthorized", { status: 401 });
  }
  revalidatePath("/");
  revalidatePath("/feed.xml");
  return Response.json({ revalidated: true });
}
