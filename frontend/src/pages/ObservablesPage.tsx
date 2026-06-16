/**
 * Observables list (Phase 2). Read-only. data_type/data/IOC flag/tags.
 */

import { useEffect, useState } from "react";

import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface ObservableRow {
  id: string;
  data_type: string;
  data: string;
  tlp: TLPValue;
  pap: string;
  tags: string[];
  is_ioc: boolean;
  sighted: boolean;
  message: string | null;
  created_at: string;
}

export function ObservablesPage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<ObservableRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const refresh = async () => {
    try {
      const r = await apiCall<ObservableRow[]>("/v1/observables?limit=500");
      setRows(r);
      setSelected(new Set());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall]);

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulkMarkIoc = async () => {
    if (selected.size === 0) return;
    setBulkBusy(true);
    try {
      const r = await apiCall<{ updated: number }>("/v1/observables/bulk-patch", {
        method: "POST",
        body: JSON.stringify({
          ids: Array.from(selected),
          patch: { is_ioc: true },
        }),
      });
      toast.success(`Marked ${r.updated} observable(s) as IOC.`);
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBulkBusy(false);
    }
  };

  const canManage = permissions.has("manageObservable");

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
    <section className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Observables</h1>
        {canManage && selected.size > 0 ? (
          <button
            type="button"
            className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
            onClick={() => {
              void bulkMarkIoc();
            }}
            disabled={bulkBusy}
          >
            {bulkBusy ? "…" : `Mark ${selected.size} as IOC`}
          </button>
        ) : null}
      </div>
      {rows.length === 0 ? (
        <p className="text-md-sys-color-on-surface-variant">No observables.</p>
      ) : (
        <table className="w-full table-auto border-collapse text-sm">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant text-left">
              <th className="py-2 pr-3" />
              <th className="py-2 pr-3">Type</th>
              <th className="py-2 pr-3">Value</th>
              <th className="py-2 pr-3">TLP</th>
              <th className="py-2 pr-3">Flags</th>
              <th className="py-2 pr-3">Tags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr
                key={o.id}
                className="border-b border-md-sys-color-outline-variant/50 hover:bg-md-sys-color-surface-container"
              >
                <td className="py-2 pr-3">
                  {canManage ? (
                    <input
                      type="checkbox"
                      checked={selected.has(o.id)}
                      onChange={() => toggleOne(o.id)}
                      aria-label={`Select ${o.data}`}
                    />
                  ) : null}
                </td>
                <td className="py-2 pr-3 font-mono text-xs">{o.data_type}</td>
                <td className="py-2 pr-3 break-all font-mono text-xs">{o.data}</td>
                <td className="py-2 pr-3">
                  <TLPBadge tlp={o.tlp} />
                </td>
                <td className="py-2 pr-3">
                  {o.is_ioc ? (
                    <span className="mr-1 rounded-full bg-severity-4/20 px-2 py-0.5 text-xs text-severity-4">
                      IOC
                    </span>
                  ) : null}
                  {o.sighted ? (
                    <span className="rounded-full bg-severity-3/20 px-2 py-0.5 text-xs text-severity-3">
                      seen
                    </span>
                  ) : null}
                </td>
                <td className="py-2 pr-3 text-xs">{o.tags.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
