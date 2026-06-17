/**
 * Alert-status distribution. Self-contained panel; consumes
 * GET /v1/stats/alerts-by-status. Renders the four triage buckets
 * (New / Updated / Ignored / Imported) as a 4-col card grid with
 * tone hints (New amber, Updated primary, Ignored muted, Imported green).
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface AlertStatusEntry {
  status: "New" | "Updated" | "Ignored" | "Imported";
  count: number;
}

interface AlertStatusResponse {
  entries: AlertStatusEntry[];
}

const STATUS_META: Record<
  AlertStatusEntry["status"],
  { toneClass: string }
> = {
  New: { toneClass: "text-severity-3" },
  Updated: { toneClass: "text-md-sys-color-primary" },
  Ignored: { toneClass: "text-md-sys-color-on-surface-variant" },
  Imported: { toneClass: "text-tlp-green" },
};

export function AlertStatusPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<AlertStatusResponse | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<AlertStatusResponse>("/v1/stats/alerts-by-status")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  const isEmpty =
    data === null ? false : data.entries.every((e) => e.count === 0);

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Alert status</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          by triage state
        </span>
      </header>
      {data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : isEmpty || data.entries.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No alerts yet.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {data.entries.map((entry) => {
            const meta = STATUS_META[entry.status];
            return (
              <div
                key={entry.status}
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
