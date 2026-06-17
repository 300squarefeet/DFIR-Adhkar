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

export function RecentAlertsPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<RecentAlert[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<RecentAlert[]>("/v1/alerts/recent?limit=10&unpromoted=true")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error).message ?? "Failed to load recent alerts.");
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Recent unpromoted alerts</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">ingest pending triage</span>
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
