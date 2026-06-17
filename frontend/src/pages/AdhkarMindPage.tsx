/**
 * Adhkar Mind (Phase 8) freeform chat. Plays through /v1/ai/freeform with
 * the stub provider by default — usable offline and audit-logged.
 */

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface FreeformResponse {
  response: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
}

interface AgentStep {
  role: string;
  content: string;
  tool_name?: string | null;
}

interface AgentRunResponse {
  final_text: string;
  tool_calls: number;
  steps: AgentStep[];
}

interface AiCallRow {
  id: string;
  provider: string;
  model: string;
  prompt: string;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
}

type Mode = "freeform" | "agent";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}

export function AdhkarMindPage() {
  const { apiCall, permissions } = useAuth();
  const canViewCalls = permissions.has("viewAudit");
  const [mode, setMode] = useState<Mode>("freeform");
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState<FreeformResponse | null>(null);
  const [agentReply, setAgentReply] = useState<AgentRunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calls, setCalls] = useState<AiCallRow[]>([]);

  const loadCalls = useCallback(() => {
    if (!canViewCalls) return;
    apiCall<AiCallRow[]>("/v1/ai/calls?limit=10")
      .then((r) => setCalls(r))
      .catch(() => setCalls([]));
  }, [apiCall, canViewCalls]);

  useEffect(() => {
    loadCalls();
  }, [loadCalls]);

  const ask = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setReply(null);
    setAgentReply(null);
    setError(null);
    try {
      if (mode === "freeform") {
        const r = await apiCall<FreeformResponse>("/v1/ai/freeform", {
          method: "POST",
          body: JSON.stringify({ prompt: prompt.trim() }),
        });
        setReply(r);
        loadCalls();
      } else {
        const r = await apiCall<AgentRunResponse>("/v1/ai/agent", {
          method: "POST",
          body: JSON.stringify({ prompt: prompt.trim(), max_steps: 5 }),
        });
        setAgentReply(r);
        loadCalls();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-6 lg:flex-row">
      <section className="max-w-3xl flex-1 space-y-4">
        <h1 className="text-2xl font-semibold">Adhkar Mind</h1>
        <p className="text-sm text-md-sys-color-on-surface-variant">
          Glass-box SOC assistant. Every call is logged with provider + model + token
          usage in the AI audit trail.
        </p>
        <div className="flex gap-2 text-sm">
          {(["freeform", "agent"] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={
                "rounded-full px-3 py-1 " +
                (mode === m
                  ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                  : "border border-md-sys-color-outline-variant")
              }
              onClick={() => setMode(m)}
            >
              {m === "freeform" ? "Freeform" : "ToolUse Agent"}
            </button>
          ))}
        </div>
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
        {agentReply ? (
          <article className="space-y-2 rounded border border-md-sys-color-outline-variant p-3">
            <p className="whitespace-pre-wrap text-sm">{agentReply.final_text}</p>
            <p className="text-xs text-md-sys-color-on-surface-variant">
              {agentReply.tool_calls} tool call{agentReply.tool_calls === 1 ? "" : "s"} ·{" "}
              {agentReply.steps.length} step{agentReply.steps.length === 1 ? "" : "s"}
            </p>
            {agentReply.steps.length > 1 ? (
              <details className="text-xs">
                <summary className="cursor-pointer text-md-sys-color-on-surface-variant">
                  Show transcript
                </summary>
                <ol className="mt-2 space-y-1">
                  {agentReply.steps.map((s, i) => (
                    <li
                      key={i}
                      className="rounded border border-md-sys-color-outline-variant/50 p-2"
                    >
                      <div className="font-mono text-[10px] uppercase text-md-sys-color-on-surface-variant">
                        {s.role}
                        {s.tool_name ? ` · ${s.tool_name}` : ""}
                      </div>
                      <pre className="whitespace-pre-wrap">{s.content}</pre>
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}
          </article>
        ) : null}
      </section>
      {canViewCalls ? (
        <aside className="space-y-2 lg:w-80 lg:flex-shrink-0">
          <h2 className="text-sm font-medium">Recent AI calls</h2>
          {calls.length === 0 ? (
            <p className="text-xs text-md-sys-color-on-surface-variant">No calls yet.</p>
          ) : (
            <ul className="space-y-2 text-xs">
              {calls.map((c) => (
                <li
                  key={c.id}
                  className="rounded border border-md-sys-color-outline-variant p-2"
                >
                  <div className="font-medium text-md-sys-color-on-surface-variant">
                    {c.provider} · {c.model}
                  </div>
                  <p className="mt-1 whitespace-pre-wrap break-words">
                    {truncate(c.prompt, 80)}
                  </p>
                  <div className="mt-1 text-[10px] text-md-sys-color-on-surface-variant">
                    {c.prompt_tokens}→{c.completion_tokens} tok · {relativeTime(c.created_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>
      ) : null}
    </div>
  );
}
