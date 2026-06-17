/**
 * ATT&CK navigator-style heatmap: per-technique case count grouped by
 * tactic. Tints each cell by case_count tier so the analyst can spot
 * the adversary's most-used techniques against this org at a glance.
 */

import { useEffect, useMemo, useState } from "react";

import { Link } from "@tanstack/react-router";

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

interface CaseStub {
  id: string;
  number: number;
  title: string;
  severity: number;
  stage: string;
}

export function AttackHeatmapPage() {
  const { apiCall } = useAuth();
  const [data, setData] = useState<HeatmapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTechnique, setActiveTechnique] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<CaseStub[]>([]);
  const [tacticFilter, setTacticFilter] = useState<string>("");

  const openTechnique = async (techniqueId: string) => {
    setActiveTechnique(techniqueId);
    try {
      const rows = await apiCall<CaseStub[]>(
        `/v1/cases-by-technique/${encodeURIComponent(techniqueId)}`,
      );
      setDrilldown(rows);
    } catch (e) {
      setError((e as Error).message);
    }
  };

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

  const filtered = useMemo(
    () =>
      tacticFilter
        ? (data?.entries.filter((e) => e.tactic === tacticFilter) ?? [])
        : (data?.entries ?? []),
    [data, tacticFilter],
  );

  const availableTactics = useMemo(() => {
    if (!data) return [] as string[];
    return Array.from(new Set(data.entries.map((e) => e.tactic))).sort();
  }, [data]);

  const byTactic = useMemo(() => {
    const m = new Map<string, HeatmapEntry[]>();
    for (const e of filtered) {
      const list = m.get(e.tactic) ?? [];
      list.push(e);
      m.set(e.tactic, list);
    }
    return m;
  }, [filtered]);

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
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-md-sys-color-on-surface-variant">
          Tactic:
        </span>
        <button
          type="button"
          aria-pressed={tacticFilter === ""}
          onClick={() => setTacticFilter("")}
          className={
            "rounded-full px-2 py-0.5 text-xs " +
            (tacticFilter === ""
              ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
              : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
          }
        >
          All
        </button>
        {availableTactics.map((t) => {
          const active = tacticFilter === t;
          return (
            <button
              key={t}
              type="button"
              aria-pressed={active}
              onClick={() => setTacticFilter(t)}
              className={
                "rounded-full px-2 py-0.5 text-xs " +
                (active
                  ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                  : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
              }
            >
              {t}
            </button>
          );
        })}
      </div>
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
                <li key={e.technique_id}>
                  <button
                    type="button"
                    onClick={() => {
                      void openTechnique(e.technique_id);
                    }}
                    className={
                      "flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:ring-1 hover:ring-md-sys-color-outline-variant " +
                      tierClass(e.case_count, max)
                    }
                  >
                    <span className="font-mono">{e.technique_id}</span>
                    <span className="truncate">{e.name}</span>
                    <span className="ml-auto font-mono">{e.case_count}</span>
                  </button>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      {activeTechnique ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3">
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-sm font-medium">
              Cases tagged with <span className="font-mono">{activeTechnique}</span> (
              {drilldown.length})
            </h2>
            <button
              type="button"
              className="ml-auto text-xs text-md-sys-color-on-surface-variant hover:underline"
              onClick={() => {
                setActiveTechnique(null);
                setDrilldown([]);
              }}
            >
              Close
            </button>
          </div>
          {drilldown.length === 0 ? (
            <p className="text-sm text-md-sys-color-on-surface-variant">
              No cases.
            </p>
          ) : (
            <ul className="space-y-1 text-sm">
              {drilldown.map((c) => (
                <li
                  key={c.id}
                  className="flex items-center gap-2 rounded border border-md-sys-color-outline-variant/50 px-3 py-1"
                >
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: c.id }}
                    className="font-mono text-xs hover:underline"
                  >
                    #{c.number}
                  </Link>
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: c.id }}
                    className="hover:underline"
                  >
                    {c.title}
                  </Link>
                  <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                    sev {c.severity} · {c.stage}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>
      ) : null}
    </section>
  );
}
