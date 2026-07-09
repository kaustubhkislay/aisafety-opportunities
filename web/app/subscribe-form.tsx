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

  if (status === "ok") {
    return <p className="py-1.5 text-sm text-[var(--brand)]">Check your inbox to confirm.</p>;
  }

  return (
    // display:contents — the input, button, and any error join the header's
    // flex row directly, so on mobile the input takes a full row and the
    // digest + Add community buttons wrap onto one tidy row together.
    <form onSubmit={onSubmit} className="contents">
      <label htmlFor="digest-email" className="sr-only">Email for the digest</label>
      <input
        id="digest-email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.org"
        className="w-full rounded bg-[var(--card)] px-3 py-1.5 text-sm shadow-[0_1px_3px_rgba(28,25,23,0.1)] focus:outline-none focus:ring-1 focus:ring-[var(--brand)] sm:w-44"
      />
      <button
        type="submit"
        disabled={status === "loading"}
        className="box-border whitespace-nowrap rounded border border-[var(--brand)] bg-[var(--brand)] px-3 py-1.5 text-center text-sm font-medium text-white transition-colors hover:bg-[var(--brand-hover)] active:translate-y-px disabled:opacity-50"
      >
        {status === "loading" ? "Subscribing…" : "Get the daily digest"}
      </button>
      {status === "error" && (
        <p className="w-full text-sm text-red-700 sm:text-right">Something went wrong. Try again.</p>
      )}
    </form>
  );
}
