/**
 * Failed dispatches sparkline. Self-contained panel; consumes
 * GET /v1/stats/notifications-per-day?status_filter=failed&days=14 and
 * renders failure counts as a Sparkline with a Σ total below.
 *
 * Hidden unless the viewer has the `manageConfig` permission, and hidden
 * when the 14-day total is zero to avoid empty-state noise on healthy
 * deployments.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { Sparkline } from "@/ui/Sparkline";

interface FailedPoint {
  day: string;
  count: number;
}

interface FailedPerDayResponse {
  series: string;
  points: FailedPoint[];
}

export function FailedDeliveriesPanel() {
  const { apiCall, permissions } = useAuth();
  const canView = permissions.has("manageConfig");
  const [data, setData] = useState<FailedPerDayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canView) return;
    let cancelled = false;
    apiCall<FailedPerDayResponse>(
      "/v1/stats/notifications-per-day?status_filter=failed&days=14",
    )
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, canView]);

  if (!canView) return null;

  const sum = data !== null ? data.points.reduce((s, p) => s + p.count, 0) : 0;

  // Hide entirely when there are no failures in the window — keeps the
  // dashboard quiet for healthy deployments.
  if (data !== null && sum === 0) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Failed dispatches (14d)</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          failures per day · last {data !== null ? data.points.length : 14}
        </span>
      </header>
      {error ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : (
        <>
          <div className="text-severity-4">
            <Sparkline
              values={data.points.map((p) => p.count)}
              width={320}
              height={48}
              ariaLabel="Failed dispatches per day"
            />
          </div>
          <p className="mt-1 text-xs text-md-sys-color-on-surface-variant">Σ {sum}</p>
        </>
      )}
    </article>
  );
}
