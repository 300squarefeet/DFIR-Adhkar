/**
 * Renders the 10 most-recently-updated unpromoted alerts from
 * /v1/alerts/recent?limit=10&unpromoted=true.
 * Self-contained: fetches once on mount.
 */

import { useContext, useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { AuthContext } from "@/lib/auth";

interface RecentAlert {
  id: string;
  source: string;
  source_ref: string;
  title: string;
  severity: number;
  status: string;
  updated_at: string;
}

function formatAge(deltaMs: number): string {
  const minutes = deltaMs / 60_000;
  const hours = minutes / 60;
  if (hours < 1) return `${Math.round(minutes)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

const SEVERITY_CHIPS: { label: string; value: number }[] = [
  { label: "S1+", value: 1 },
  { label: "S2+", value: 2 },
  { label: "S3+", value: 3 },
  { label: "S4", value: 4 },
];

export function RecentAlertsPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<RecentAlert[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [minSeverity, setMinSeverity] = useState<number>(0);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    const url =
      minSeverity >= 1
        ? `/v1/alerts/recent?limit=10&unpromoted=true&severity_gte=${minSeverity}`
        : "/v1/alerts/recent?limit=10&unpromoted=true";
    apiCall<RecentAlert[]>(url)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error).message ?? "Failed to load recent alerts.");
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, minSeverity]);

  if (!apiCall) return null;

  const chipClass = (active: boolean) =>
    `rounded-full px-2 py-0.5 text-xs ${
      active
        ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
        : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container"
    }`;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Recent unpromoted alerts</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">ingest pending triage</span>
        <div className="ml-auto flex items-center gap-1" role="group" aria-label="Severity filter">
          <button
            type="button"
            className={chipClass(minSeverity === 0)}
            onClick={() => setMinSeverity(0)}
            aria-pressed={minSeverity === 0}
          >
            All
          </button>
          {SEVERITY_CHIPS.map((chip) => (
            <button
              key={chip.value}
              type="button"
              className={chipClass(minSeverity === chip.value)}
              onClick={() => setMinSeverity(chip.value)}
              aria-pressed={minSeverity === chip.value}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No pending alerts.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.map((a) => (
            <li key={a.id} className="flex items-center gap-2">
              <Link
                to="/alerts/$alertId"
                params={{ alertId: a.id }}
                className="font-mono hover:underline"
              >
                {a.source}/{a.source_ref}
              </Link>
              <span className="truncate">{a.title}</span>
              <div className="ml-auto flex shrink-0 items-center gap-2">
                <SeverityBadge level={a.severity as SeverityLevel} />
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  updated {formatAge(Date.now() - new Date(a.updated_at).getTime())}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
