/**
 * Cases list (Phase 3) with:
 * - Saved views (stage filter + assignee filter) persisted to localStorage.
 * - Bulk select + bulk PATCH (close N cases at once).
 */

import { useEffect, useMemo, useState } from "react";

import { Link } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { useUserNames } from "@/lib/useUserNames";
import { useToast } from "@/ui/Toast";

interface CaseRow {
  id: string;
  number: number;
  title: string;
  severity: SeverityLevel;
  tlp: TLPValue;
  stage: string;
  status: string;
  tags: string[];
  assignee_id: string | null;
  updated_at: string;
}

type StageFilter = "" | "open" | "in_progress" | "closed";

interface SavedView {
  stage: StageFilter;
  search: string;
  severity: "" | "1" | "2" | "3" | "4";
  tag: string;
  flagged: "" | "true" | "false";
  since: string;
  until: string;
}

const SAVED_VIEW_KEY = "adhkar.cases.savedView.v1";

const EMPTY_VIEW: SavedView = {
  stage: "",
  search: "",
  severity: "",
  tag: "",
  flagged: "",
  since: "",
  until: "",
};

function loadSavedView(): SavedView {
  try {
    const raw = window.localStorage.getItem(SAVED_VIEW_KEY);
    if (!raw) return EMPTY_VIEW;
    const parsed = JSON.parse(raw) as Partial<SavedView>;
    return {
      stage: parsed.stage ?? "",
      search: parsed.search ?? "",
      severity: parsed.severity ?? "",
      tag: parsed.tag ?? "",
      flagged: parsed.flagged ?? "",
      since: parsed.since ?? "",
      until: parsed.until ?? "",
    };
  } catch {
    return EMPTY_VIEW;
  }
}

export function CasesPage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [cases, setCases] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<SavedView>(() => loadSavedView());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const refresh = async () => {
    try {
      const p = new URLSearchParams({ limit: "200" });
      if (view.stage) p.set("stage", view.stage);
      if (view.severity) p.set("severity", view.severity);
      if (view.tag.trim()) p.set("tag", view.tag.trim());
      if (view.flagged) p.set("flagged", view.flagged);
      if (view.since) p.set("since", new Date(view.since).toISOString());
      if (view.until) p.set("until", new Date(view.until).toISOString());
      const rows = await apiCall<CaseRow[]>(`/v1/cases?${p.toString()}`);
      setCases(rows);
      setSelected(new Set());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // refresh dependency captured below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    apiCall,
    view.stage,
    view.severity,
    view.tag,
    view.flagged,
    view.since,
    view.until,
  ]);

  useEffect(() => {
    window.localStorage.setItem(SAVED_VIEW_KEY, JSON.stringify(view));
  }, [view]);

  const assigneeNames = useUserNames(cases?.map((c) => c.assignee_id) ?? []);

  const filtered = useMemo(() => {
    if (!cases) return [];
    const q = view.search.trim().toLowerCase();
    if (!q) return cases;
    return cases.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.tags.some((t) => t.toLowerCase().includes(q)) ||
        String(c.number).includes(q) ||
        (c.assignee_id &&
          (assigneeNames[c.assignee_id] ?? "").toLowerCase().includes(q)),
    );
  }, [cases, view.search, assigneeNames]);

  const toggleAll = (checked: boolean) => {
    if (!checked) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(filtered.map((c) => c.id)));
  };

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulkClose = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Close ${selected.size} case${selected.size === 1 ? "" : "s"}?`))
      return;
    setBulkBusy(true);
    try {
      const r = await apiCall<{ updated: number }>("/v1/cases/bulk-patch", {
        method: "POST",
        body: JSON.stringify({
          ids: Array.from(selected),
          patch: { stage: "closed", status: "Closed" },
        }),
      });
      toast.success(`Closed ${r.updated} case${r.updated === 1 ? "" : "s"}.`);
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBulkBusy(false);
    }
  };

  if (error) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Cases</h1>
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          Failed to load cases: {error}
        </p>
      </section>
    );
  }

  if (cases === null) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Cases</h1>
        <p className="text-md-sys-color-on-surface-variant">Loading…</p>
      </section>
    );
  }

  const allChecked = filtered.length > 0 && filtered.every((c) => selected.has(c.id));

  return (
    <section className="p-6">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Cases</h1>
        <div className="ml-auto flex items-center gap-2">
          <a
            href={(() => {
              const base =
                (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
                "http://localhost:8000";
              const p = new URLSearchParams();
              if (view.stage) p.set("stage", view.stage);
              if (view.severity) p.set("severity", view.severity);
              if (view.flagged) p.set("flagged", view.flagged);
              if (view.tag.trim()) p.set("tag", view.tag.trim());
              if (view.since) p.set("since", new Date(view.since).toISOString());
              if (view.until) p.set("until", new Date(view.until).toISOString());
              const qs = p.toString();
              return `${base}/v1/cases/export-csv${qs ? `?${qs}` : ""}`;
            })()}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
          >
            Export CSV
          </a>
          {permissions.has("manageCase") ? (
            <Link
              to="/cases/new"
              className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary"
            >
              + New Case
            </Link>
          ) : null}
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={view.stage}
          onChange={(e) => setView({ ...view, stage: e.target.value as StageFilter })}
        >
          <option value="">All stages</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="closed">Closed</option>
        </select>
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={view.severity}
          onChange={(e) =>
            setView({
              ...view,
              severity: e.target.value as SavedView["severity"],
            })
          }
        >
          <option value="">All severities</option>
          <option value="1">S1 (info)</option>
          <option value="2">S2 (low)</option>
          <option value="3">S3 (med)</option>
          <option value="4">S4 (high)</option>
        </select>
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={view.flagged}
          onChange={(e) =>
            setView({
              ...view,
              flagged: e.target.value as SavedView["flagged"],
            })
          }
        >
          <option value="">All flags</option>
          <option value="true">Flagged</option>
          <option value="false">Unflagged</option>
        </select>
        <input
          className="w-32 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Tag…"
          value={view.tag}
          onChange={(e) => setView({ ...view, tag: e.target.value })}
        />
        <input
          type="date"
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={view.since}
          onChange={(e) => setView({ ...view, since: e.target.value })}
          title="Created since"
        />
        <input
          type="date"
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={view.until}
          onChange={(e) => setView({ ...view, until: e.target.value })}
          title="Created until (exclusive)"
        />
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Filter title / tag / #number…"
          value={view.search}
          onChange={(e) => setView({ ...view, search: e.target.value })}
        />
        {permissions.has("manageCase") && selected.size > 0 ? (
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

      {filtered.length === 0 ? (
        <p className="text-md-sys-color-on-surface-variant">No cases match this view.</p>
      ) : (
        <table className="w-full table-auto border-collapse text-sm">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant text-left">
              <th className="py-2 pr-3">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={(e) => toggleAll(e.target.checked)}
                  aria-label="Select all visible"
                />
              </th>
              <th className="py-2 pr-3">#</th>
              <th className="py-2 pr-3">Title</th>
              <th className="py-2 pr-3">Severity</th>
              <th className="py-2 pr-3">TLP</th>
              <th className="py-2 pr-3">Assignee</th>
              <th className="py-2 pr-3">Stage</th>
              <th className="py-2 pr-3">Updated</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr
                key={c.id}
                className="border-b border-md-sys-color-outline-variant/50 hover:bg-md-sys-color-surface-container"
              >
                <td className="py-2 pr-3">
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={() => toggleOne(c.id)}
                    aria-label={`Select case #${c.number}`}
                  />
                </td>
                <td className="py-2 pr-3 font-mono">
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: c.id }}
                    className="hover:underline"
                  >
                    #{c.number}
                  </Link>
                </td>
                <td className="py-2 pr-3">
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: c.id }}
                    className="hover:underline"
                  >
                    {c.title}
                  </Link>
                </td>
                <td className="py-2 pr-3">
                  <SeverityBadge level={c.severity} compact />
                </td>
                <td className="py-2 pr-3">
                  <TLPBadge tlp={c.tlp} />
                </td>
                <td className="py-2 pr-3 text-xs">
                  {c.assignee_id ? (
                    assigneeNames[c.assignee_id] ?? c.assignee_id.slice(0, 8)
                  ) : (
                    <span className="text-md-sys-color-on-surface-variant">
                      unassigned
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3">{c.stage}</td>
                <td className="py-2 pr-3 text-md-sys-color-on-surface-variant">
                  {new Date(c.updated_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
