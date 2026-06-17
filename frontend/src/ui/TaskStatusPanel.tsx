/**
 * Task-status distribution. Self-contained panel; consumes
 * GET /v1/stats/tasks-by-status. Renders the four lifecycle buckets
 * (Waiting / InProgress / Completed / Cancelled) as a 4-col card grid
 * with tone hints and per-card aria-label.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface TaskStatusEntry {
  status: "Waiting" | "InProgress" | "Completed" | "Cancelled";
  count: number;
}

interface TaskStatusResponse {
  entries: TaskStatusEntry[];
}

const STATUS_META: Record<
  TaskStatusEntry["status"],
  { toneClass: string }
> = {
  Waiting: { toneClass: "text-md-sys-color-on-surface-variant" },
  InProgress: { toneClass: "text-md-sys-color-primary" },
  Completed: { toneClass: "text-tlp-green" },
  Cancelled: { toneClass: "text-md-sys-color-on-surface-variant" },
};

export function TaskStatusPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<TaskStatusResponse>("/v1/stats/tasks-by-status")
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

  const hasData = data !== null && data.entries.some((e) => e.count > 0);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Task status</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          by lifecycle stage
        </span>
      </header>
      {error ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : !hasData ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No tasks yet.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {data.entries.map((entry) => {
            const meta = STATUS_META[entry.status];
            return (
              <div
                key={entry.status}
                aria-label={`${entry.status}: ${entry.count} tasks`}
                className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface-container p-3"
              >
                <div className={`text-3xl font-semibold ${meta.toneClass}`}>
                  {entry.count}
                </div>
                <div className="mt-1 text-xs text-md-sys-color-on-surface-variant">
                  {entry.status}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </article>
  );
}
