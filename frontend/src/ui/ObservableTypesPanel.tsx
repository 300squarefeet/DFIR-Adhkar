/**
 * IOC composition by data_type. Self-contained panel; consumes
 * GET /v1/stats/observables-by-type. Renders a top-N row of buckets with a
 * count + a tiny horizontal bar relative to the largest bucket.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface Bucket {
  data_type: string;
  count: number;
}

interface Response {
  entries: Bucket[];
}

export function ObservableTypesPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<Response | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<Response>("/v1/stats/observables-by-type")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  const top = data?.entries.slice(0, 8) ?? [];
  const max = top.reduce((m, b) => (b.count > m ? b.count : m), 0);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">IOC composition</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          by observable type — top {top.length}
        </span>
      </header>
      {data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : top.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No observables yet.
        </p>
      ) : (
        <ul className="space-y-1 text-xs">
          {top.map((b) => {
            const pct = max > 0 ? Math.round((b.count / max) * 100) : 0;
            return (
              <li key={b.data_type} className="flex items-center gap-2">
                <span className="w-24 truncate font-mono">{b.data_type}</span>
                <div
                  className="h-2 rounded bg-md-sys-color-primary"
                  style={{ width: `${pct}%`, minWidth: "2px" }}
                  aria-hidden
                />
                <span className="ml-auto tabular-nums">{b.count}</span>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}
