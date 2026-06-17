/**
 * Alert source panel. Consumes GET /v1/stats/alerts-by-source?limit=10 (RC116).
 * Renders the top-10 noisiest ingest sources as labeled bars sized by count
 * relative to the largest. Helps analysts spot which feed is flooding the queue.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface Entry {
  source: string;
  count: number;
}

interface Response {
  entries: Entry[];
}

export function AlertSourcePanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<Response>("/v1/stats/alerts-by-source?limit=10")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  const top = data?.entries ?? [];
  const hasData = data !== null && !data.entries.every((r) => r.count === 0);
  const max = Math.max(...top.map((r) => r.count), 1);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Alert sources</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          top by ingest volume
        </span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : !hasData ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No alerts yet.</p>
      ) : (
        <ul className="space-y-1 text-xs">
          {top.map((row) => {
            const pct = Math.round((row.count / max) * 100);
            return (
              <li
                key={row.source}
                className="flex items-center gap-2"
                aria-label={`${row.source}: ${row.count} alerts`}
              >
                <span className="w-40 truncate font-mono">{row.source}</span>
                <div
                  className="h-2 rounded bg-md-sys-color-primary"
                  style={{ width: `${pct}%`, minWidth: "2px" }}
                  aria-hidden
                />
                <span className="ml-auto tabular-nums">{row.count}</span>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}
