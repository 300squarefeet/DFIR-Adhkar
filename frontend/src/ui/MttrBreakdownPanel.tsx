/**
 * Renders the four severity buckets from /v1/stats/case-mttr as a small
 * row of cards. Self-contained: fetches on mount + when `days` changes.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface MttrBucket {
  severity: number;
  closed_count: number;
  median_hours: number | null;
  mean_hours: number | null;
}

interface MttrResponse {
  window_days: number;
  buckets: MttrBucket[];
}

const SEV_LABEL: Record<number, string> = {
  1: "S1 (info)",
  2: "S2 (low)",
  3: "S3 (med)",
  4: "S4 (high)",
};

const SEV_TONE: Record<number, string> = {
  1: "text-md-sys-color-on-surface",
  2: "text-md-sys-color-on-surface",
  3: "text-severity-3",
  4: "text-severity-4",
};

function formatHours(h: number | null): string {
  if (h === null) return "—";
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(1)} h`;
  return `${(h / 24).toFixed(1)} d`;
}

export function MttrBreakdownPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<MttrResponse | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<MttrResponse>(`/v1/stats/case-mttr?days=${days}`)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall, days]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Case MTTR by severity</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          rolling {data?.window_days ?? days}-day window
        </span>
        <select
          className="ml-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-0.5 text-xs"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          title="Window length"
        >
          <option value={7}>7d</option>
          <option value={30}>30d</option>
          <option value={90}>90d</option>
          <option value={365}>1y</option>
        </select>
      </header>
      {data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {data.buckets.map((b) => (
            <div
              key={b.severity}
              className="rounded border border-md-sys-color-outline-variant/60 p-2"
            >
              <div
                className={
                  "text-xl font-semibold " + (SEV_TONE[b.severity] ?? "")
                }
              >
                {formatHours(b.median_hours)}
              </div>
              <div className="text-xs text-md-sys-color-on-surface-variant">
                {SEV_LABEL[b.severity] ?? `S${b.severity}`} · median
              </div>
              <div className="text-[10px] text-md-sys-color-on-surface-variant">
                mean {formatHours(b.mean_hours)} · n={b.closed_count}
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
