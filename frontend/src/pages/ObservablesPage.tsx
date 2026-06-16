/**
 * Observables list (Phase 2). Read-only. data_type/data/IOC flag/tags.
 */

import { useEffect, useState } from "react";

import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

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
  const { apiCall } = useAuth();
  const [rows, setRows] = useState<ObservableRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiCall<ObservableRow[]>("/v1/observables")
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
      <h1 className="mb-4 text-2xl font-semibold">Observables</h1>
      {rows.length === 0 ? (
        <p className="text-md-sys-color-on-surface-variant">No observables.</p>
      ) : (
        <table className="w-full table-auto border-collapse text-sm">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant text-left">
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
