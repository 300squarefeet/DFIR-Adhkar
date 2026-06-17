/**
 * Renders the 10 most-recently-updated tasks assigned to the current analyst
 * from /v1/tasks/recent?limit=10&mine=true.
 * Self-contained: fetches once on mount.
 */

import { useContext, useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { AuthContext } from "@/lib/auth";

interface RecentTask {
  id: string;
  case_id: string;
  title: string;
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

export function RecentTasksPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<RecentTask[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<RecentTask[]>("/v1/tasks/recent?limit=10&mine=true")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error).message ?? "Failed to load recent tasks.");
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">My recent tasks</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">assigned to me, last updated</span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No recent tasks assigned to you.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.map((t) => (
            <li key={t.id} className="flex items-center gap-2">
              <Link
                to="/cases/$caseId"
                params={{ caseId: t.case_id }}
                className="font-mono hover:underline"
              >
                case {t.case_id.slice(0, 8)}
              </Link>
              <span className="truncate">{t.title}</span>
              <div className="ml-auto flex shrink-0 items-center gap-2">
                <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] uppercase">
                  {t.status}
                </span>
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  updated {formatAge(Date.now() - new Date(t.updated_at).getTime())}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
