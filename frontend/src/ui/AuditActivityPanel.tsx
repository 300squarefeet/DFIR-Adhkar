/**
 * Audit activity sparkline. Self-contained panel; consumes
 * GET /v1/stats/audit-per-day?days=14 and renders event counts
 * as a Sparkline with a Σ total below.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";
import { Sparkline } from "@/ui/Sparkline";

interface AuditPoint {
  day: string;
  count: number;
}

interface AuditPerDayResponse {
  series: string;
  points: AuditPoint[];
}

export function AuditActivityPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<AuditPerDayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<AuditPerDayResponse>("/v1/stats/audit-per-day?days=14")
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

  const sum = data !== null ? data.points.reduce((s, p) => s + p.count, 0) : 0;
  const isEmpty = data !== null && sum === 0;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Audit activity</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          events per day · last {data !== null ? data.points.length : 14}
        </span>
      </header>
      {error ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : isEmpty ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No audit activity in this window.
        </p>
      ) : (
        <>
          <div className="text-md-sys-color-primary">
            <Sparkline
              values={data.points.map((p) => p.count)}
              width={320}
              height={48}
              ariaLabel="Audit events per day"
            />
          </div>
          <p className="mt-1 text-xs text-md-sys-color-on-surface-variant">Σ {sum}</p>
        </>
      )}
    </article>
  );
}
