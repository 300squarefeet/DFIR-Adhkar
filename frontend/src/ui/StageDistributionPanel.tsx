/**
 * Case-stage distribution. Self-contained panel; consumes
 * GET /v1/stats/case-stages. Renders the three lifecycle buckets
 * (Open / In progress / Closed) as a 3-col grid of count cards with
 * tone hints (open default, in_progress amber, closed green).
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface StageEntry {
  stage: "open" | "in_progress" | "closed";
  count: number;
}

interface StageResponse {
  entries: StageEntry[];
}

const STAGE_META: Record<
  StageEntry["stage"],
  { label: string; toneClass: string }
> = {
  open: { label: "Open", toneClass: "text-md-sys-color-on-surface" },
  in_progress: { label: "In progress", toneClass: "text-severity-3" },
  closed: { label: "Closed", toneClass: "text-tlp-green" },
};

export function StageDistributionPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<StageResponse | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<StageResponse>("/v1/stats/case-stages")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  const isEmpty =
    data === null ? false : data.entries.every((e) => e.count === 0);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Case stages</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          by lifecycle stage
        </span>
      </header>
      {data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : isEmpty || data.entries.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No cases yet.
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {data.entries.map((entry) => {
            const meta = STAGE_META[entry.stage];
            return (
              <div
                key={entry.stage}
                className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface-container p-3"
              >
                <div className={`text-3xl font-semibold ${meta.toneClass}`}>
                  {entry.count}
                </div>
                <div className="mt-1 text-xs text-md-sys-color-on-surface-variant">
                  {meta.label}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </article>
  );
}
