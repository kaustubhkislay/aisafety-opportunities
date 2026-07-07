export async function POST(req: Request): Promise<Response> {
  let message = "";
  let email = "";
  try {
    const body = await req.json();
    message = typeof body?.message === "string" ? body.message.trim() : "";
    email = typeof body?.email === "string" ? body.email.trim() : "";
  } catch {
    return Response.json({ error: "bad request" }, { status: 400 });
  }

  if (!message || message.length > 5000) {
    return Response.json({ error: "message must be 1-5000 characters" }, { status: 400 });
  }

  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return Response.json({ error: "feedback not configured" }, { status: 500 });
  }

  const res = await fetch(`${backend}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, email }),
  });
  if (!res.ok) {
    return Response.json({ error: "feedback failed" }, { status: res.status });
  }
  return Response.json(await res.json());
}
