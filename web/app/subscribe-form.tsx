"use client";

import { useState } from "react";

type Status = "idle" | "loading" | "ok" | "error";

export function SubscribeForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setStatus("ok");
        setEmail("");
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
      <label htmlFor="digest-email" className="sr-only">Email for the digest</label>
      <input
        id="digest-email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.org"
        className="rounded border border-gray-300 px-3 py-1.5 text-sm"
      />
      <button
        type="submit"
        disabled={status === "loading"}
        className="rounded bg-gray-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
      >
        {status === "loading" ? "Subscribing…" : "Get the digest"}
      </button>
      {status === "ok" && <span className="text-sm text-green-700">Subscribed — check your inbox.</span>}
      {status === "error" && <span className="text-sm text-red-700">Something went wrong. Try again.</span>}
    </form>
  );
}
