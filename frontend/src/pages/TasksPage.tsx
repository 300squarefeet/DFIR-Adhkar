/**
 * Cross-case task queue (Phase 3).
 * Filter by status; group visually by case_id.
 */

import { useEffect, useMemo, useState } from "react";

import { Link } from "@tanstack/react-router";

import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

type TaskStatus = "Waiting" | "InProgress" | "Completed" | "Cancelled";

interface TaskRow {
  id: string;
  case_id: string;
  title: string;
  group: string | null;
  status: TaskStatus;
  assignee_id: string | null;
  due_date: string | null;
  order_index: number;
  mandatory: boolean;
  updated_at: string;
}

const STATUS_OPTIONS: TaskStatus[] = ["Waiting", "InProgress", "Completed", "Cancelled"];

export function TasksPage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<TaskRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus | "">("");

  const refresh = async () => {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (status) params.set("status_filter", status);
      const r = await apiCall<TaskRow[]>(`/v1/tasks?${params.toString()}`);
      setRows(r);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall, status]);

  const groupedByCase = useMemo(() => {
    if (!rows) return new Map<string, TaskRow[]>();
    const m = new Map<string, TaskRow[]>();
    for (const r of rows) {
      const list = m.get(r.case_id) ?? [];
      list.push(r);
      m.set(r.case_id, list);
    }
    return m;
  }, [rows]);

  const setTaskStatus = async (t: TaskRow, next: TaskStatus) => {
    try {
      await apiCall<TaskRow>(`/v1/tasks/${t.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      toast.success(`Task "${t.title}" → ${next}`);
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (rows === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <select
          className="ml-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value as TaskStatus | "")}
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      {groupedByCase.size === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">No tasks.</p>
      ) : (
        <ul className="space-y-3">
          {Array.from(groupedByCase.entries()).map(([caseId, tasks]) => (
            <li
              key={caseId}
              className="rounded border border-md-sys-color-outline-variant p-3"
            >
              <h2 className="mb-2 text-xs font-medium text-md-sys-color-on-surface-variant">
                <Link
                  to="/cases/$caseId"
                  params={{ caseId }}
                  className="font-mono hover:underline"
                >
                  case {caseId.slice(0, 8)}
                </Link>{" "}
                — {tasks.length} task{tasks.length === 1 ? "" : "s"}
              </h2>
              <ul className="space-y-1 text-sm">
                {tasks.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center gap-2 rounded border border-md-sys-color-outline-variant/50 px-3 py-1.5"
                  >
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-[10px] uppercase " +
                        (t.status === "InProgress"
                          ? "bg-md-sys-color-primary/20 text-md-sys-color-primary"
                          : t.status === "Completed"
                            ? "bg-tlp-green/20 text-tlp-green"
                            : t.status === "Cancelled"
                              ? "bg-md-sys-color-surface-container"
                              : "bg-md-sys-color-surface-container")
                      }
                    >
                      {t.status}
                    </span>
                    <span>{t.title}</span>
                    {t.mandatory ? (
                      <span className="text-xs text-severity-3">required</span>
                    ) : null}
                    {t.due_date ? (
                      <span className="text-xs text-md-sys-color-on-surface-variant">
                        due {new Date(t.due_date).toLocaleDateString()}
                      </span>
                    ) : null}
                    {permissions.has("manageTask") ? (
                      <select
                        className="ml-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-0.5 text-xs"
                        value={t.status}
                        onChange={(e) => {
                          void setTaskStatus(t, e.target.value as TaskStatus);
                        }}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    ) : null}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
