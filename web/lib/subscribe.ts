// Email-digest subscribe helpers (Slice 6 / T4.1).
// The form posts to /api/subscribe, which forwards to the backend (server-side,
// so the backend URL is never exposed to the browser).

export function isValidEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test((value ?? "").trim());
}

export interface SubscribeResult {
  ok: boolean;
  status: number;
  data?: unknown;
}

export async function forwardSubscribe(
  email: string,
  backendUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SubscribeResult> {
  const res = await fetchImpl(`${backendUrl}/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  return { ok: res.ok, status: res.status, data: res.ok ? await res.json() : undefined };
}
