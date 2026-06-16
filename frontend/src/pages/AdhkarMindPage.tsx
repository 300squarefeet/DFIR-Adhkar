/**
 * Adhkar Mind (Phase 8) freeform chat. Plays through /v1/ai/freeform with
 * the stub provider by default — usable offline and audit-logged.
 */

import { useState } from "react";

import { useAuth } from "@/lib/auth";

interface FreeformResponse {
  response: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
}

export function AdhkarMindPage() {
  const { apiCall } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState<FreeformResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setReply(null);
    setError(null);
    try {
      const r = await apiCall<FreeformResponse>("/v1/ai/freeform", {
        method: "POST",
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      setReply(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Adhkar Mind</h1>
      <p className="text-sm text-md-sys-color-on-surface-variant">
        Glass-box SOC assistant. Every call is logged with provider + model + token
        usage in the AI audit trail.
      </p>
      <textarea
        className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
        rows={5}
        placeholder="Ask Adhkar Mind…"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <button
        type="button"
        className="rounded-full bg-md-sys-color-primary px-4 py-2 text-sm text-md-sys-color-on-primary disabled:opacity-50"
        onClick={() => {
          void ask();
        }}
        disabled={busy || !prompt.trim()}
      >
        {busy ? "Thinking…" : "Ask"}
      </button>
      {error ? (
        <p role="alert" className="rounded bg-severity-4/20 p-2 text-sm text-severity-4">
          {error}
        </p>
      ) : null}
      {reply ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3">
          <p className="whitespace-pre-wrap text-sm">{reply.response}</p>
          <p className="mt-2 text-xs text-md-sys-color-on-surface-variant">
            {reply.provider}/{reply.model} · in {reply.input_tokens} tok · out{" "}
            {reply.output_tokens} tok
          </p>
        </article>
      ) : null}
    </section>
  );
}
