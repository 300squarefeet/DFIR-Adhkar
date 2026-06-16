/**
 * ATT&CK navigator-style heatmap: per-technique case count grouped by
 * tactic. Tints each cell by case_count tier so the analyst can spot
 * the adversary's most-used techniques against this org at a glance.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";

interface HeatmapEntry {
  technique_id: string;
  name: string;
  tactic: string;
  case_count: number;
}

interface HeatmapResponse {
  entries: HeatmapEntry[];
}

function tierClass(count: number, max: number): string {
  if (max <= 0) return "bg-md-sys-color-surface-container";
  const ratio = count / max;
  if (ratio >= 0.75) return "bg-severity-4/30 text-severity-4";
  if (ratio >= 0.5) return "bg-severity-3/30 text-severity-3";
  if (ratio >= 0.25) return "bg-severity-2/30 text-severity-2";
  return "bg-severity-1/20";
}

export function AttackHeatmapPage() {
  const { apiCall } = useAuth();
  const [data, setData] = useState<HeatmapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiCall<HeatmapResponse>("/v1/stats/ttps-heatmap")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  const byTactic = useMemo(() => {
    const m = new Map<string, HeatmapEntry[]>();
    if (!data) return m;
    for (const e of data.entries) {
      const list = m.get(e.tactic) ?? [];
      list.push(e);
      m.set(e.tactic, list);
    }
    return m;
  }, [data]);

  const max = useMemo(() => {
    if (!data) return 0;
    return data.entries.reduce((m, e) => Math.max(m, e.case_count), 0);
  }, [data]);

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (data === null) return <section className="p-6">Loading…</section>;
  if (data.entries.length === 0)
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">ATT&amp;CK Heatmap</h1>
        <p className="text-sm text-md-sys-color-on-surface-variant">
          No techniques mapped to cases yet. Add MITRE techniques on a case
          via the &ldquo;MITRE ATT&amp;CK&rdquo; section in the case detail view.
        </p>
      </section>
    );

  const tactics = Array.from(byTactic.keys()).sort();

  return (
    <section className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">ATT&amp;CK Heatmap</h1>
      <p className="text-sm text-md-sys-color-on-surface-variant">
        Per-technique case count for this org, grouped by tactic. Darker
        tiles = more cases. Max observed: {max}.
      </p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {tactics.map((tactic) => (
          <article
            key={tactic}
            className="rounded border border-md-sys-color-outline-variant p-3"
          >
            <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-md-sys-color-on-surface-variant">
              {tactic}
            </h2>
            <ul className="space-y-1 text-xs">
              {(byTactic.get(tactic) ?? []).map((e) => (
                <li
                  key={e.technique_id}
                  className={
                    "flex items-center gap-2 rounded px-2 py-1 " + tierClass(e.case_count, max)
                  }
                >
                  <span className="font-mono">{e.technique_id}</span>
                  <span className="truncate">{e.name}</span>
                  <span className="ml-auto font-mono">{e.case_count}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
