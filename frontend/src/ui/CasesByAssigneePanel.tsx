/**
 * Analyst workload panel. Consumes GET /v1/stats/cases-by-assignee (RC106).
 * Renders top-8 assignees as rows with a horizontal bar sized by open_count
 * relative to the largest bucket, plus per-row aria-label. Resolves
 * assignee_id → display_name via useUserNames; null bucket labelled
 * 'unassigned'. Empty state when all counts are zero.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";
import { useUserNames } from "@/lib/useUserNames";

interface Entry {
  assignee_id: string | null;
  open_count: number;
  closed_count: number;
}

interface Response {
  entries: Entry[];
}

export function CasesByAssigneePanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<Response>("/v1/stats/cases-by-assignee")
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

  const top = data?.entries.slice(0, 8) ?? [];
  const names = useUserNames(top.map((e) => e.assignee_id));

  if (!apiCall) return null;

  const hasData =
    data !== null && data.entries.some((e) => e.open_count > 0 || e.closed_count > 0);
  const max_open = Math.max(...top.map((e) => e.open_count), 1);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Analyst workload</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          open / closed cases per assignee
        </span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : !hasData ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No assigned cases yet.</p>
      ) : (
        <ul className="space-y-1 text-xs">
          {top.map((e) => {
            const name =
              e.assignee_id !== null
                ? (names[e.assignee_id] ?? e.assignee_id.slice(0, 8))
                : "unassigned";
            const pct = Math.round((e.open_count / max_open) * 100);
            return (
              <li
                key={e.assignee_id ?? "__unassigned__"}
                className="flex items-center gap-2"
                aria-label={`${name}: ${e.open_count} open, ${e.closed_count} closed`}
              >
                <span className="w-40 truncate font-mono">{name}</span>
                <div
                  className="h-2 rounded bg-md-sys-color-primary"
                  style={{ width: `${pct}%`, minWidth: "2px" }}
                  aria-hidden
                />
                <span className="font-mono tabular-nums">
                  {e.open_count} open · {e.closed_count} closed
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}
