import { isValidEmail, forwardSubscribe } from "@/lib/subscribe";

export async function POST(req: Request): Promise<Response> {
  let email = "";
  try {
    const body = await req.json();
    email = typeof body?.email === "string" ? body.email.trim() : "";
  } catch {
    return Response.json({ error: "bad request" }, { status: 400 });
  }

  if (!isValidEmail(email)) {
    return Response.json({ error: "invalid email" }, { status: 400 });
  }

  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return Response.json({ error: "subscribe not configured" }, { status: 500 });
  }

  const result = await forwardSubscribe(email, backend);
  if (!result.ok) {
    return Response.json({ error: "subscribe failed" }, { status: result.status });
  }
  return Response.json(result.data);
}
