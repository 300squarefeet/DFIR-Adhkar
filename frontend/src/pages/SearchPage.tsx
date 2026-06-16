/**
 * Unified search across cases + alerts (Phase 6).
 * Hits the backend FTS path; results link to the matching detail page.
 */

import { useState } from "react";

import { Link } from "@tanstack/react-router";

import { useAuth } from "@/lib/auth";

interface SearchHit {
  entity_type: "case" | "alert";
  id: string;
  title: string;
  score: number;
}

interface SearchResponse {
  query: string;
  hits: SearchHit[];
}

export function SearchPage() {
  const { apiCall } = useAuth();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await apiCall<SearchResponse>(
        `/v1/search?q=${encodeURIComponent(q.trim())}&limit=25`,
      );
      setResults(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Search</h1>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
          placeholder="Search cases + alerts…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void run();
          }}
        />
        <button
          type="button"
          className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
          onClick={() => {
            void run();
          }}
          disabled={busy || !q.trim()}
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </div>
      {error ? (
        <p role="alert" className="rounded bg-severity-4/20 p-2 text-sm text-severity-4">
          {error}
        </p>
      ) : null}
      {results ? (
        results.hits.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            No matches for &ldquo;{results.query}&rdquo;.
          </p>
        ) : (
          <ul className="space-y-1">
            {results.hits.map((h) => (
              <li
                key={`${h.entity_type}-${h.id}`}
                className="rounded border border-md-sys-color-outline-variant px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2">
                  <span className="rounded bg-md-sys-color-surface-container px-1.5 py-0.5 font-mono text-[10px] uppercase">
                    {h.entity_type}
                  </span>
                  {h.entity_type === "case" ? (
                    <Link
                      to="/cases/$caseId"
                      params={{ caseId: h.id }}
                      className="font-medium hover:underline"
                    >
                      {h.title}
                    </Link>
                  ) : (
                    <span className="font-medium">{h.title}</span>
                  )}
                  <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                    score {h.score.toFixed(3)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </section>
  );
}
