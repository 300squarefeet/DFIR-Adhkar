/**
 * Active this week panel. Consumes GET /v1/users/recent (RC164) with
 * ?limit=10&active_within_days=7. Silent panel: hidden when the viewer
 * lacks the `viewCase` permission (same gate as the backend endpoint)
 * and hidden when the result list is empty so healthy dashboards stay
 * quiet. Renders display_name (falling back to email) with a status
 * chip per row, capped at 10 entries.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface RecentUser {
  id: string;
  email: string;
  display_name: string;
  status: string;
}

export function RecentActiveUsersPanel() {
  const { apiCall, permissions } = useAuth();
  const canView = permissions.has("viewCase");
  const [data, setData] = useState<RecentUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canView) return;
    let cancelled = false;
    apiCall<RecentUser[]>("/v1/users/recent?limit=10&active_within_days=7")
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
  if (data !== null && data.length === 0) return null;

  const rows = data?.slice(0, 10) ?? [];

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Active this week</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          users seen in the last 7 days
        </span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : (
        <ul className="space-y-1">
          {rows.map((u) => {
            const label = u.display_name !== "" ? u.display_name : u.email;
            const chipClass =
              u.status === "active"
                ? "bg-md-sys-color-tertiary"
                : u.status === "suspended"
                  ? "bg-severity-3/20"
                  : "bg-md-sys-color-surface-container";
            return (
              <li key={u.id} className="flex items-center gap-2 text-sm">
                <span className="truncate">{label}</span>
                <span
                  className={"ml-auto rounded px-1.5 text-xs font-mono " + chipClass}
                >
                  {u.status}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}
