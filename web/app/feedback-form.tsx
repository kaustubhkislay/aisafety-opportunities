"use client";

import { useState } from "react";

type Status = "idle" | "loading" | "ok" | "error";

export function FeedbackForm() {
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, email }),
      });
      if (res.ok) {
        setStatus("ok");
        setMessage("");
        setEmail("");
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  }

  if (status === "ok") {
    return <p className="text-sm text-[var(--brand)]">Thanks — feedback received.</p>;
  }

  return (
    <form onSubmit={onSubmit} className="flex max-w-xl flex-col gap-2">
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="What's missing, broken, or worth adding?"
        rows={3}
        required
        maxLength={5000}
        className="border border-[var(--edge)] bg-[var(--card)] p-2 text-sm focus:border-[var(--brand)] focus:outline-none"
      />
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email (optional, if you want a reply)"
          className="min-w-[14rem] flex-1 border-b border-[var(--edge)] bg-transparent px-1 py-1.5 text-sm focus:border-[var(--brand)] focus:outline-none"
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="rounded bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--brand-hover)] active:translate-y-px disabled:opacity-50"
        >
          Send feedback
        </button>
      </div>
      {status === "error" && (
        <p className="text-sm text-red-700">Something went wrong — please try again.</p>
      )}
    </form>
  );
}
