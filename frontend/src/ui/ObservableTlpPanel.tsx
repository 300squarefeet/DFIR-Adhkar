/**
 * IOC TLP composition. Consumes GET /v1/stats/observables-by-tlp.
 * Renders the five canonical TLP buckets as labeled bars relative to
 * the largest bucket. Mirrors RC93a/RC91a shape: null-safe AuthContext,
 * error state, hasData boolean, aria-label per card.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface Bucket {
  tlp: string;
  count: number;
}

interface Response {
  entries: Bucket[];
}

const TLP_META: Record<string, { label: string; barClass: string }> = {
  white: { label: "TLP:WHITE", barClass: "bg-tlp-white" },
  green: { label: "TLP:GREEN", barClass: "bg-tlp-green" },
  amber: { label: "TLP:AMBER", barClass: "bg-tlp-amber" },
  "amber-strict": { label: "TLP:AMBER+STRICT", barClass: "bg-tlp-amber-strict" },
  red: { label: "TLP:RED", barClass: "bg-tlp-red" },
};

export function ObservableTlpPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<Response>("/v1/stats/observables-by-tlp")
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

  const hasData = data !== null && data.entries.some((b) => b.count > 0);
  const max =
    data === null ? 0 : data.entries.reduce((m, b) => (b.count > m ? b.count : m), 0);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">IOC by TLP</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          observable distribution
        </span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : !hasData ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No observables yet.
        </p>
      ) : (
        <ul className="space-y-1 text-xs">
          {data.entries.map((b) => {
            const meta = TLP_META[b.tlp] ?? { label: b.tlp, barClass: "bg-md-sys-color-primary" };
            const pct = max > 0 ? Math.round((b.count / max) * 100) : 0;
            return (
              <li
                key={b.tlp}
                className="flex items-center gap-2"
                aria-label={`${meta.label}: ${b.count} observables`}
              >
                <span className="w-36 truncate font-mono">{meta.label}</span>
                <div
                  className={"h-2 rounded " + meta.barClass}
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
