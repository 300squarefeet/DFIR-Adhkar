/**
 * Cross-case task queue (Phase 3).
 * Filter by status; group visually by case_id.
 */

import { useEffect, useMemo, useState } from "react";

import { Link } from "@tanstack/react-router";

import { useAuth } from "@/lib/auth";
import { useUserNames } from "@/lib/useUserNames";
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
  const urlOverride = (() => {
    if (typeof window === "undefined")
      return {} as {
        status?: TaskStatus | "";
        mine?: boolean;
        overdue?: boolean;
        mandatory?: "" | "true" | "false";
        due_within_days?: number | null;
        updated_within_hours?: 0 | 24 | 168 | 720;
      };
    const p = new URLSearchParams(window.location.search);
    const out: {
      status?: TaskStatus | "";
      mine?: boolean;
      overdue?: boolean;
      mandatory?: "" | "true" | "false";
      due_within_days?: number | null;
      updated_within_hours?: 0 | 24 | 168 | 720;
    } = {};
    const s = p.get("status_filter");
    if (s === "Waiting" || s === "InProgress" || s === "Completed" || s === "Cancelled")
      out.status = s;
    if (p.get("mine") === "true") out.mine = true;
    if (p.get("overdue") === "true") out.overdue = true;
    const m = p.get("mandatory");
    if (m === "true" || m === "false") out.mandatory = m;
    const d = p.get("due_within_days");
    if (d !== null) {
      const n = Number.parseInt(d, 10);
      if (Number.isFinite(n) && n >= 1 && n <= 90) out.due_within_days = n;
    }
    const u = p.get("updated_within_hours");
    if (u !== null) {
      const n = Number.parseInt(u, 10);
      if (n === 0 || n === 24 || n === 168 || n === 720) out.updated_within_hours = n;
    }
    return out;
  })();
  const initialView = (() => {
    try {
      const raw = window.localStorage.getItem("adhkar.tasks.savedView.v1");
      if (!raw)
        return {
          status: "" as TaskStatus | "",
          mine: false,
          overdue: false,
          mandatory: "" as "" | "true" | "false",
          due_within_days: null as number | null,
          updated_within_hours: 0 as 0 | 24 | 168 | 720,
        };
      const p = JSON.parse(raw) as {
        status?: TaskStatus | "";
        mine?: boolean;
        overdue?: boolean;
        mandatory?: "" | "true" | "false";
        due_within_days?: number | null;
        updated_within_hours?: 0 | 24 | 168 | 720;
      };
      const dRaw = p.due_within_days;
      const dNorm =
        typeof dRaw === "number" && Number.isFinite(dRaw) && dRaw >= 1 && dRaw <= 90
          ? dRaw
          : null;
      const uRaw = p.updated_within_hours;
      const uNorm: 0 | 24 | 168 | 720 =
        uRaw === 24 || uRaw === 168 || uRaw === 720 ? uRaw : 0;
      return {
        status: (p.status ?? "") as TaskStatus | "",
        mine: Boolean(p.mine),
        overdue: Boolean(p.overdue),
        mandatory: (p.mandatory ?? "") as "" | "true" | "false",
        due_within_days: dNorm,
        updated_within_hours: uNorm,
      };
    } catch {
      return {
        status: "" as TaskStatus | "",
        mine: false,
        overdue: false,
        mandatory: "" as "" | "true" | "false",
        due_within_days: null as number | null,
        updated_within_hours: 0 as 0 | 24 | 168 | 720,
      };
    }
  })();
  const [status, setStatus] = useState<TaskStatus | "">(
    urlOverride.status ?? initialView.status,
  );
  const [mine, setMine] = useState(urlOverride.mine ?? initialView.mine);
  const [overdue, setOverdue] = useState(
    urlOverride.overdue ?? initialView.overdue,
  );
  const [mandatory, setMandatory] = useState<"" | "true" | "false">(
    urlOverride.mandatory ?? initialView.mandatory,
  );
  const [dueWithin, setDueWithin] = useState<number | null>(
    urlOverride.due_within_days ?? initialView.due_within_days,
  );
  const [updatedWithinHours, setUpdatedWithinHours] = useState<0 | 24 | 168 | 720>(
    urlOverride.updated_within_hours ?? initialView.updated_within_hours,
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const toggleSelected = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const bulkClose = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Close ${selected.size} task(s)?`)) return;
    setBulkBusy(true);
    try {
      const r = await apiCall<{ updated: number }>("/v1/tasks/bulk-patch", {
        method: "POST",
        body: JSON.stringify({
          ids: Array.from(selected),
          patch: { status: "Completed" },
        }),
      });
      toast.success(`Closed ${r.updated} task(s).`);
      setSelected(new Set());
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBulkBusy(false);
    }
  };
  useEffect(() => {
    try {
      window.localStorage.setItem(
        "adhkar.tasks.savedView.v1",
        JSON.stringify({
          status,
          mine,
          overdue,
          mandatory,
          due_within_days: dueWithin,
          updated_within_hours: updatedWithinHours,
        }),
      );
    } catch {
      /* private mode — best-effort */
    }
  }, [status, mine, overdue, mandatory, dueWithin, updatedWithinHours]);

  const refresh = async () => {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (status) params.set("status_filter", status);
      if (mine) params.set("mine", "true");
      // dueWithin and overdue are mutually exclusive: when dueWithin is set,
      // don't send overdue (preserves the user's saved toggle for re-selection).
      if (dueWithin !== null && dueWithin >= 1) {
        params.set("due_within_days", String(dueWithin));
      } else if (overdue) {
        params.set("overdue", "true");
      }
      if (mandatory) params.set("mandatory", mandatory);
      if (updatedWithinHours >= 1) {
        params.set(
          "updated_since",
          new Date(Date.now() - updatedWithinHours * 3600 * 1000).toISOString(),
        );
      }
      const r = await apiCall<TaskRow[]>(`/v1/tasks?${params.toString()}`);
      setRows(r);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall, status, mine, overdue, mandatory, dueWithin, updatedWithinHours]);

  const userNames = useUserNames(rows?.map((r) => r.assignee_id) ?? []);

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
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <button
          type="button"
          className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
          onClick={() => {
            const p = new URLSearchParams();
            if (status) p.set("status_filter", status);
            if (mine) p.set("mine", "true");
            if (dueWithin !== null && dueWithin >= 1) {
              p.set("due_within_days", String(dueWithin));
            } else if (overdue) {
              p.set("overdue", "true");
            }
            if (mandatory) p.set("mandatory", mandatory);
            if (updatedWithinHours >= 1) {
              p.set("updated_within_hours", String(updatedWithinHours));
              p.set(
                "updated_since",
                new Date(Date.now() - updatedWithinHours * 3600 * 1000).toISOString(),
              );
            }
            const qs = p.toString();
            const url = `${window.location.origin}/tasks${qs ? `?${qs}` : ""}`;
            navigator.clipboard
              .writeText(url)
              .then(() => toast.success("Link copied."))
              .catch(() => toast.error("Clipboard unavailable."));
          }}
          title="Copy a link to this filtered view"
        >
          Copy URL
        </button>
        <a
          href={(() => {
            const base =
              (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
              "http://localhost:8000";
            const p = new URLSearchParams();
            if (status) p.set("status_filter", status);
            if (mine) p.set("mine", "true");
            if (dueWithin !== null && dueWithin >= 1) {
              p.set("due_within_days", String(dueWithin));
            } else if (overdue) {
              p.set("overdue", "true");
            }
            if (mandatory) p.set("mandatory", mandatory);
            if (updatedWithinHours >= 1) {
              p.set(
                "updated_since",
                new Date(Date.now() - updatedWithinHours * 3600 * 1000).toISOString(),
              );
            }
            const qs = p.toString();
            return `${base}/v1/tasks/export-csv${qs ? `?${qs}` : ""}`;
          })()}
          target="_blank"
          rel="noreferrer"
          className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
        >
          Export CSV
        </a>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={mine}
            onChange={(e) => setMine(e.target.checked)}
          />
          Mine
        </label>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={overdue}
            onChange={(e) => setOverdue(e.target.checked)}
          />
          Overdue
        </label>
        <div className="flex items-center gap-1 text-sm" role="group" aria-label="Due within filter">
          <span className="text-md-sys-color-on-surface-variant">Due:</span>
          {([
            { label: "Any", value: null },
            { label: "7d", value: 7 },
            { label: "30d", value: 30 },
          ] as const).map((chip) => {
            const active = dueWithin === chip.value;
            return (
              <button
                key={chip.label}
                type="button"
                aria-pressed={active}
                onClick={() => setDueWithin(chip.value)}
                className={
                  "rounded-full px-2 py-0.5 text-xs " +
                  (active
                    ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                    : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
                }
              >
                {chip.label}
              </button>
            );
          })}
        </div>
        <div
          className="flex items-center gap-1 text-sm"
          role="group"
          aria-label="Edited within filter"
        >
          <span className="text-md-sys-color-on-surface-variant">Edited:</span>
          {(
            [
              { label: "Any", value: 0 },
              { label: "24h", value: 24 },
              { label: "7d", value: 168 },
              { label: "30d", value: 720 },
            ] as const
          ).map((chip) => {
            const active = updatedWithinHours === chip.value;
            return (
              <button
                key={chip.label}
                type="button"
                aria-pressed={active}
                onClick={() => setUpdatedWithinHours(chip.value)}
                className={
                  "rounded-full px-2 py-0.5 text-xs " +
                  (active
                    ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                    : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
                }
              >
                {chip.label}
              </button>
            );
          })}
        </div>
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={mandatory}
          onChange={(e) =>
            setMandatory(e.target.value as "" | "true" | "false")
          }
          title="Mandatory-task filter"
        >
          <option value="">All tasks</option>
          <option value="true">Mandatory</option>
          <option value="false">Optional</option>
        </select>
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
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
        {permissions.has("manageTask") && selected.size > 0 ? (
          <button
            type="button"
            className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
            onClick={() => {
              void bulkClose();
            }}
            disabled={bulkBusy}
          >
            {bulkBusy ? "Closing…" : `Close ${selected.size}`}
          </button>
        ) : null}
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
                    {permissions.has("manageTask") &&
                    t.status !== "Completed" &&
                    t.status !== "Cancelled" ? (
                      <input
                        type="checkbox"
                        checked={selected.has(t.id)}
                        onChange={() => toggleSelected(t.id)}
                        aria-label={`Select task ${t.title}`}
                      />
                    ) : null}
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
                    {t.assignee_id ? (
                      <span className="text-xs text-md-sys-color-on-surface-variant">
                        @
                        {userNames[t.assignee_id] ?? t.assignee_id.slice(0, 8)}
                      </span>
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
