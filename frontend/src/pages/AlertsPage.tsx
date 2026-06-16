/**
 * Alerts triage list (Phase 4). Read + promote-to-case.
 */

import { useEffect, useState } from "react";

import { Link, useRouter } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface AlertRow {
  id: string;
  type: string;
  source: string;
  source_ref: string;
  title: string;
  severity: SeverityLevel;
  tlp: TLPValue;
  status: string;
  case_id: string | null;
  created_at: string;
}

interface PromoteResponse {
  case_id: string;
  case_number: number;
}

const SAVED_VIEW_KEY = "adhkar.alerts.savedView.v1";

interface SavedView {
  status: string;
  source: string;
  search: string;
}

function loadView(): SavedView {
  try {
    const raw = window.localStorage.getItem(SAVED_VIEW_KEY);
    if (!raw) return { status: "", source: "", search: "" };
    const p = JSON.parse(raw) as Partial<SavedView>;
    return { status: p.status ?? "", source: p.source ?? "", search: p.search ?? "" };
  } catch {
    return { status: "", source: "", search: "" };
  }
}

export function AlertsPage() {
  const { apiCall, permissions } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [alerts, setAlerts] = useState<AlertRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [promotingId, setPromotingId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [view, setView] = useState<SavedView>(() => loadView());

  const refresh = async () => {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (view.status) params.set("alert_status", view.status);
      if (view.source) params.set("source", view.source);
      const rows = await apiCall<AlertRow[]>(`/v1/alerts?${params.toString()}`);
      setAlerts(rows);
      setSelected(new Set());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall, view.status, view.source]);

  useEffect(() => {
    window.localStorage.setItem(SAVED_VIEW_KEY, JSON.stringify(view));
  }, [view]);

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = (checked: boolean) => {
    if (!alerts || !checked) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(alerts.filter((a) => a.case_id === null).map((a) => a.id)));
  };

  const bulkIgnore = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Mark ${selected.size} alert(s) as Ignored?`)) return;
    setBulkBusy(true);
    try {
      const r = await apiCall<{ updated: number }>("/v1/alerts/bulk-patch", {
        method: "POST",
        body: JSON.stringify({
          ids: Array.from(selected),
          patch: { status: "Ignored" },
        }),
      });
      toast.success(`Ignored ${r.updated} alert(s).`);
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBulkBusy(false);
    }
  };

  const promote = async (alertId: string) => {
    setPromotingId(alertId);
    try {
      const r = await apiCall<PromoteResponse>(`/v1/alerts/${alertId}/promote`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      await router.navigate({ to: "/cases/$caseId", params: { caseId: r.case_id } });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPromotingId(null);
    }
  };

  if (error) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Alerts</h1>
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  }
  if (alerts === null) return <section className="p-6">Loading…</section>;
  if (alerts.length === 0) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Alerts</h1>
        <p className="text-md-sys-color-on-surface-variant">No alerts.</p>
      </section>
    );
  }

  const canManage = permissions.has("manageAlert");
  const allCheckable = (alerts ?? []).filter((a) => a.case_id === null);
  const allChecked = allCheckable.length > 0 && allCheckable.every((a) => selected.has(a.id));

  const visible = (alerts ?? []).filter((a) => {
    const q = view.search.trim().toLowerCase();
    if (!q) return true;
    return (
      a.title.toLowerCase().includes(q) ||
      a.source.toLowerCase().includes(q) ||
      a.source_ref.toLowerCase().includes(q)
    );
  });

  return (
    <section className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Alerts</h1>
        {canManage && selected.size > 0 ? (
          <button
            type="button"
            className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
            onClick={() => {
              void bulkIgnore();
            }}
            disabled={bulkBusy}
          >
            {bulkBusy ? "…" : `Ignore ${selected.size}`}
          </button>
        ) : null}
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={view.status}
          onChange={(e) => setView({ ...view, status: e.target.value })}
        >
          <option value="">All statuses</option>
          <option value="New">New</option>
          <option value="Updated">Updated</option>
          <option value="Ignored">Ignored</option>
          <option value="Imported">Imported</option>
        </select>
        <input
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Source filter (e.g. splunk)"
          value={view.source}
          onChange={(e) => setView({ ...view, source: e.target.value })}
        />
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Local filter (title / source_ref)"
          value={view.search}
          onChange={(e) => setView({ ...view, search: e.target.value })}
        />
      </div>
      <table className="w-full table-auto border-collapse text-sm">
        <thead>
          <tr className="border-b border-md-sys-color-outline-variant text-left">
            <th className="py-2 pr-3">
              {canManage ? (
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={(e) => toggleAll(e.target.checked)}
                  aria-label="Select all unpromoted alerts"
                />
              ) : null}
            </th>
            <th className="py-2 pr-3">Source</th>
            <th className="py-2 pr-3">Title</th>
            <th className="py-2 pr-3">Severity</th>
            <th className="py-2 pr-3">TLP</th>
            <th className="py-2 pr-3">Status</th>
            <th className="py-2 pr-3" />
          </tr>
        </thead>
        <tbody>
          {visible.map((a) => (
            <tr
              key={a.id}
              className="border-b border-md-sys-color-outline-variant/50 hover:bg-md-sys-color-surface-container"
            >
              <td className="py-2 pr-3">
                {canManage && a.case_id === null ? (
                  <input
                    type="checkbox"
                    checked={selected.has(a.id)}
                    onChange={() => toggleOne(a.id)}
                    aria-label={`Select ${a.source_ref}`}
                  />
                ) : null}
              </td>
              <td className="py-2 pr-3 font-mono text-xs">
                <Link
                  to="/alerts/$alertId"
                  params={{ alertId: a.id }}
                  className="hover:underline"
                >
                  {a.source}/{a.source_ref}
                </Link>
              </td>
              <td className="py-2 pr-3">
                <Link
                  to="/alerts/$alertId"
                  params={{ alertId: a.id }}
                  className="hover:underline"
                >
                  {a.title}
                </Link>
              </td>
              <td className="py-2 pr-3">
                <SeverityBadge level={a.severity} compact />
              </td>
              <td className="py-2 pr-3">
                <TLPBadge tlp={a.tlp} />
              </td>
              <td className="py-2 pr-3">{a.status}</td>
              <td className="py-2 pr-3">
                {a.case_id === null && permissions.has("manageCase") ? (
                  <button
                    type="button"
                    className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
                    onClick={() => {
                      void promote(a.id);
                    }}
                    disabled={promotingId === a.id}
                  >
                    {promotingId === a.id ? "Promoting…" : "Promote → Case"}
                  </button>
                ) : a.case_id !== null ? (
                  <span className="text-xs text-md-sys-color-on-surface-variant">
                    promoted
                  </span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
