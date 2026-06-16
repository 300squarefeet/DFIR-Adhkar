/**
 * Taxonomies viewer (Phase 6 extras).
 * List + filter by namespace; admin-only inline create.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface TaxonomyEntry {
  id: string;
  namespace: string;
  predicate: string;
  value: string;
  description: string | null;
  color: string | null;
}

export function TaxonomiesPage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<TaxonomyEntry[] | null>(null);
  const [filter, setFilter] = useState("");
  const [namespace, setNamespace] = useState("");
  const [predicate, setPredicate] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canManage = permissions.has("manageConfig");

  const refresh = async () => {
    try {
      const r = await apiCall<TaxonomyEntry[]>("/v1/taxonomies");
      setRows(r);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall]);

  const namespaces = useMemo(() => {
    if (!rows) return [] as string[];
    return Array.from(new Set(rows.map((r) => r.namespace))).sort();
  }, [rows]);

  const visible = useMemo(() => {
    if (!rows) return [] as TaxonomyEntry[];
    const q = filter.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (!q ||
          r.namespace.toLowerCase().includes(q) ||
          r.predicate.toLowerCase().includes(q) ||
          r.value.toLowerCase().includes(q)) &&
        (namespace === "" || r.namespace === namespace),
    );
  }, [rows, filter, namespace]);

  const [scope, setScope] = useState<string>("");

  const create = async () => {
    if (!scope.trim() || !predicate.trim() || !value.trim()) return;
    setBusy(true);
    try {
      await apiCall("/v1/taxonomies", {
        method: "POST",
        body: JSON.stringify({
          namespace: scope.trim(),
          predicate: predicate.trim(),
          value: value.trim(),
        }),
      });
      toast.success("Entry created.");
      setPredicate("");
      setValue("");
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
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
      <h1 className="text-2xl font-semibold">Taxonomies</h1>
      <p className="text-sm text-md-sys-color-on-surface-variant">
        MISP-style namespace:predicate=value vocabulary for tagging cases,
        alerts, and observables.
      </p>
      <div className="flex flex-wrap gap-2">
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={namespace}
          onChange={(e) => setNamespace(e.target.value)}
        >
          <option value="">All namespaces</option>
          {namespaces.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {canManage ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3">
          <h2 className="mb-2 text-sm font-medium">+ Entry</h2>
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="namespace"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            />
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="predicate"
              value={predicate}
              onChange={(e) => setPredicate(e.target.value)}
            />
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="value"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <button
              type="button"
              className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void create();
              }}
              disabled={busy || !scope.trim() || !predicate.trim() || !value.trim()}
            >
              {busy ? "…" : "Add"}
            </button>
          </div>
        </article>
      ) : null}

      {visible.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">No entries.</p>
      ) : (
        <table className="w-full table-auto border-collapse text-sm">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant text-left">
              <th className="py-2 pr-3">Namespace</th>
              <th className="py-2 pr-3">Predicate</th>
              <th className="py-2 pr-3">Value</th>
              <th className="py-2 pr-3">Description</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr
                key={r.id}
                className="border-b border-md-sys-color-outline-variant/50"
              >
                <td className="py-2 pr-3 font-mono text-xs">{r.namespace}</td>
                <td className="py-2 pr-3 font-mono text-xs">{r.predicate}</td>
                <td className="py-2 pr-3 font-mono text-xs">{r.value}</td>
                <td className="py-2 pr-3 text-xs text-md-sys-color-on-surface-variant">
                  {r.description ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
