/**
 * MITRE ATT&CK catalog viewer (Phase 5).
 * Filterable list of TTP catalog entries.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";

interface CatalogRow {
  id: string;
  technique_id: string;
  name: string;
  tactic: string;
  description: string | null;
  url: string | null;
  is_subtechnique: boolean;
}

export function TtpsPage() {
  const { apiCall } = useAuth();
  const [rows, setRows] = useState<CatalogRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [tactic, setTactic] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    apiCall<CatalogRow[]>("/v1/ttps/catalog?limit=500")
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  const tactics = useMemo(() => {
    if (!rows) return [];
    return Array.from(new Set(rows.map((r) => r.tactic))).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    if (!rows) return [];
    const q = filter.trim().toLowerCase();
    return rows.filter((r) => {
      if (tactic && r.tactic !== tactic) return false;
      if (!q) return true;
      return (
        r.technique_id.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        (r.description?.toLowerCase().includes(q) ?? false)
      );
    });
  }, [rows, filter, tactic]);

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
      <h1 className="mb-4 text-2xl font-semibold">MITRE ATT&amp;CK Catalog</h1>
      <div className="mb-3 flex flex-wrap gap-2">
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Filter T-ID, name, description…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={tactic}
          onChange={(e) => setTactic(e.target.value)}
        >
          <option value="">All tactics</option>
          {tactics.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      {filtered.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">
          {rows.length === 0
            ? "Catalog empty. Have an admin POST to /v1/ttps/catalog to seed."
            : "No matches."}
        </p>
      ) : (
        <ul className="space-y-1 text-sm">
          {filtered.slice(0, 200).map((r) => (
            <li
              key={r.id}
              className="rounded border border-md-sys-color-outline-variant px-3 py-2"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-md-sys-color-on-surface-variant">
                  {r.technique_id}
                </span>
                <span className="font-medium">{r.name}</span>
                <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                  {r.tactic}
                </span>
              </div>
              {r.description ? (
                <p className="mt-1 text-xs text-md-sys-color-on-surface-variant">
                  {r.description}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {filtered.length > 200 ? (
        <p className="mt-2 text-xs text-md-sys-color-on-surface-variant">
          showing first 200 of {filtered.length}
        </p>
      ) : null}
    </section>
  );
}
