import { revalidatePath } from "next/cache";

export async function POST(req: Request): Promise<Response> {
  const secret = new URL(req.url).searchParams.get("secret");
  const expected = process.env.REVALIDATE_SECRET;
  if (!expected || secret !== expected) {
    return new Response("unauthorized", { status: 401 });
  }
  revalidatePath("/");
  revalidatePath("/feed.xml");
  revalidatePath("/partners"); // partner list derives from the same records
  return Response.json({ revalidated: true });
}
