/**
 * Renders the 10 most-recently-updated cases assigned to the current user
 * from /v1/cases/recent?mine=true.
 * Self-contained: fetches once on mount.
 */

import { useContext, useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { AuthContext } from "@/lib/auth";

interface RecentCase {
  id: string;
  number: number;
  title: string;
  severity: number;
  updated_at: string;
}

function formatAge(deltaMs: number): string {
  const minutes = deltaMs / 60_000;
  const hours = minutes / 60;
  if (hours < 1) return `${Math.round(minutes)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export function MyRecentCasesPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<RecentCase[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<RecentCase[]>("/v1/cases/recent?mine=true&limit=10")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error).message ?? "Failed to load recent cases.");
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">My recent cases</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">assigned to me, last updated</span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No cases assigned to you yet.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.map((c) => (
            <li key={c.id} className="flex items-center gap-2">
              <Link
                to="/cases/$caseId"
                params={{ caseId: c.id }}
                className="font-mono hover:underline"
              >
                #{c.number}
              </Link>
              <span className="truncate">{c.title}</span>
              <div className="ml-auto flex shrink-0 items-center gap-2">
                <SeverityBadge level={c.severity as SeverityLevel} />
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  updated {formatAge(Date.now() - new Date(c.updated_at).getTime())}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
