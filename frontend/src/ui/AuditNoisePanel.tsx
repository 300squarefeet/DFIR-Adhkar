/**
 * Audit noise panel. Consumes GET /v1/audit/summary?days=14 (RC108).
 * Renders the top-5 noisiest (entity_type, action) buckets as
 * "entity.action" labels with horizontal bars sized by count relative
 * to the largest bucket. Helps analysts spot a sudden spike of mutations
 * on one entity family or a chatty automation rule.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface Row {
  entity_type: string;
  action: string;
  count: number;
}

interface Response {
  window_days: number;
  rows: Row[];
}

export function AuditNoisePanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<Response>("/v1/audit/summary?days=14")
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

  const windowDays = data?.window_days ?? 14;
  const top = data?.rows.slice(0, 5) ?? [];
  const hasData = data !== null && !data.rows.every((r) => r.count === 0);
  const max = Math.max(...top.map((r) => r.count), 1);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Audit noise</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          top buckets, last {windowDays}d
        </span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : !hasData ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No audit activity in this window.
        </p>
      ) : (
        <ul className="space-y-1 text-xs">
          {top.map((row) => {
            const pct = Math.round((row.count / max) * 100);
            return (
              <li
                key={`${row.entity_type}.${row.action}`}
                className="flex items-center gap-2"
                aria-label={`${row.entity_type}.${row.action}: ${row.count} events`}
              >
                <span className="w-40 truncate font-mono">
                  {row.entity_type}.{row.action}
                </span>
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
