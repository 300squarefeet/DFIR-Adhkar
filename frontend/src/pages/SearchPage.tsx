/**
 * Unified search across cases + alerts (Phase 6).
 * Hits the backend FTS path; results link to the matching detail page.
 */

import { useEffect, useState } from "react";

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

const RECENT_KEY = "adhkar.search.recent.v1";
const RECENT_MAX = 8;

function loadRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? (parsed as unknown[]).filter((x): x is string => typeof x === "string")
      : [];
  } catch {
    return [];
  }
}

export function SearchPage() {
  const { apiCall } = useAuth();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>(() => loadRecent());
  const [entityType, setEntityType] = useState<"" | "case" | "alert">("");
  const [minSev, setMinSev] = useState<"" | "1" | "2" | "3" | "4">("");

  useEffect(() => {
    try {
      window.localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
    } catch {
      /* best-effort */
    }
  }, [recent]);

  const run = async (override?: string) => {
    const term = (override ?? q).trim();
    if (!term) return;
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams({ q: term, limit: "25" });
      if (entityType) params.set("entity_type", entityType);
      if (minSev) params.set("min_severity", minSev);
      const r = await apiCall<SearchResponse>(
        `/v1/search?${params.toString()}`,
      );
      setResults(r);
      setRecent((prev) =>
        [term, ...prev.filter((x) => x !== term)].slice(0, RECENT_MAX),
      );
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
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-md-sys-color-on-surface-variant">Scope:</span>
        {[
          { v: "", label: "All" },
          { v: "case", label: "Cases" },
          { v: "alert", label: "Alerts" },
        ].map((opt) => (
          <button
            key={opt.v}
            type="button"
            className={
              "rounded-full border px-2 py-0.5 " +
              (entityType === opt.v
                ? "border-md-sys-color-primary bg-md-sys-color-primary text-md-sys-color-on-primary"
                : "border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
            }
            onClick={() => setEntityType(opt.v as "" | "case" | "alert")}
          >
            {opt.label}
          </button>
        ))}
        <span className="ml-2 text-md-sys-color-on-surface-variant">
          Min severity:
        </span>
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-0.5"
          value={minSev}
          onChange={(e) =>
            setMinSev(e.target.value as "" | "1" | "2" | "3" | "4")
          }
        >
          <option value="">any</option>
          <option value="1">S1+</option>
          <option value="2">S2+</option>
          <option value="3">S3+</option>
          <option value="4">S4</option>
        </select>
      </div>
      {recent.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-md-sys-color-on-surface-variant">Recent:</span>
          {recent.map((term) => (
            <button
              key={term}
              type="button"
              className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 hover:bg-md-sys-color-surface-container"
              onClick={() => {
                setQ(term);
                void run(term);
              }}
              title="Re-run this query"
            >
              {term}
            </button>
          ))}
          <button
            type="button"
            className="ml-auto text-md-sys-color-on-surface-variant hover:underline"
            onClick={() => setRecent([])}
          >
            Clear history
          </button>
        </div>
      ) : null}
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
