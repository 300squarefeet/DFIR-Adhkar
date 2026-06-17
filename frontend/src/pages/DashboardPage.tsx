/**
 * Dashboard (Phase 6) — widget-driven. Each WidgetSpec declares its own
 * endpoint and how to derive its KPI; results are deduped per endpoint so
 * we don't refetch the same list multiple times.
 */

import { Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";
import { AlertStatusPanel } from "@/ui/AlertStatusPanel";
import { AuditActivityPanel } from "@/ui/AuditActivityPanel";
import { CasesByAssigneePanel } from "@/ui/CasesByAssigneePanel";
import { MttrBreakdownPanel } from "@/ui/MttrBreakdownPanel";
import { ObservableTlpPanel } from "@/ui/ObservableTlpPanel";
import { ObservableTypesPanel } from "@/ui/ObservableTypesPanel";
import { PinnedRunbooksPanel } from "@/ui/PinnedRunbooksPanel";
import { SlowestOpenCasesPanel } from "@/ui/SlowestOpenCasesPanel";
import { Sparkline } from "@/ui/Sparkline";
import { StageDistributionPanel } from "@/ui/StageDistributionPanel";
import { CORE_WIDGETS, type WidgetSpec } from "@/ui/widgets";

interface TimeSeriesPoint {
  day: string;
  count: number;
}

interface TimeSeriesResponse {
  series: string;
  points: TimeSeriesPoint[];
}

const LAYOUT_KEY = "adhkar.dashboard.layout.v1";

interface DashboardLayout {
  order: string[];
  hidden: string[];
}

function loadLayout(): DashboardLayout {
  try {
    const raw = window.localStorage.getItem(LAYOUT_KEY);
    if (!raw) return { order: CORE_WIDGETS.map((w) => w.id), hidden: [] };
    const parsed = JSON.parse(raw) as Partial<DashboardLayout>;
    const order = Array.isArray(parsed.order)
      ? parsed.order.filter((id) => CORE_WIDGETS.some((w) => w.id === id))
      : [];
    const known = new Set(order);
    for (const w of CORE_WIDGETS) {
      if (!known.has(w.id)) order.push(w.id);
    }
    const hidden = Array.isArray(parsed.hidden) ? parsed.hidden : [];
    return { order, hidden };
  } catch {
    return { order: CORE_WIDGETS.map((w) => w.id), hidden: [] };
  }
}

export function DashboardPage() {
  const { apiCall } = useAuth();
  const [responses, setResponses] = useState<Record<string, unknown>>({});
  const [casesSeries, setCasesSeries] = useState<TimeSeriesResponse | null>(null);
  const [alertsSeries, setAlertsSeries] = useState<TimeSeriesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layout, setLayout] = useState<DashboardLayout>(() => loadLayout());
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [c, a] = await Promise.all([
          apiCall<TimeSeriesResponse>("/v1/stats/cases-per-day?days=14"),
          apiCall<TimeSeriesResponse>("/v1/stats/alerts-per-day?days=14"),
        ]);
        if (cancelled) return;
        setCasesSeries(c);
        setAlertsSeries(a);
      } catch {
        // silent — KPI cards still render
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  useEffect(() => {
    window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
  }, [layout]);

  const uniquePaths = useMemo(() => {
    const set = new Set<string>();
    for (const w of CORE_WIDGETS) set.add(w.path);
    return Array.from(set);
  }, []);

  const orderedWidgets: WidgetSpec[] = useMemo(() => {
    const byId = new Map(CORE_WIDGETS.map((w) => [w.id, w] as const));
    return layout.order
      .map((id) => byId.get(id))
      .filter((w): w is WidgetSpec => w !== undefined);
  }, [layout.order]);

  const visibleWidgets = orderedWidgets.filter((w) => !layout.hidden.includes(w.id));

  const move = (id: string, delta: -1 | 1) => {
    setLayout((prev) => {
      const idx = prev.order.indexOf(id);
      if (idx < 0) return prev;
      const next = [...prev.order];
      const target = idx + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target] as string, next[idx] as string];
      return { ...prev, order: next };
    });
  };

  const toggleHidden = (id: string) => {
    setLayout((prev) => ({
      ...prev,
      hidden: prev.hidden.includes(id)
        ? prev.hidden.filter((x) => x !== id)
        : [...prev.hidden, id],
    }));
  };

  const resetLayout = () => {
    setLayout({ order: CORE_WIDGETS.map((w) => w.id), hidden: [] });
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const pairs = await Promise.all(
          uniquePaths.map(async (p) => [p, await apiCall<unknown>(p)] as const),
        );
        if (cancelled) return;
        setResponses(Object.fromEntries(pairs));
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, uniquePaths]);

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );

  const loaded = uniquePaths.every((p) => p in responses);

  return (
    <section className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <button
          type="button"
          className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
          onClick={() => setEditing((v) => !v)}
        >
          {editing ? "Done" : "Customize"}
        </button>
        {editing ? (
          <button
            type="button"
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
            onClick={resetLayout}
          >
            Reset
          </button>
        ) : null}
      </div>
      {casesSeries || alertsSeries ? (
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {casesSeries ? (
            <div className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-4">
              <div className="mb-2 flex items-baseline justify-between">
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  Cases per day · last {casesSeries.points.length}
                </span>
                <span className="font-mono text-sm">
                  Σ {casesSeries.points.reduce((s, p) => s + p.count, 0)}
                </span>
              </div>
              <div className="text-md-sys-color-primary">
                <Sparkline
                  values={casesSeries.points.map((p) => p.count)}
                  width={320}
                  height={48}
                  ariaLabel="Cases per day"
                />
              </div>
            </div>
          ) : null}
          {alertsSeries ? (
            <div className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-4">
              <div className="mb-2 flex items-baseline justify-between">
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  Alerts per day · last {alertsSeries.points.length}
                </span>
                <span className="font-mono text-sm">
                  Σ {alertsSeries.points.reduce((s, p) => s + p.count, 0)}
                </span>
              </div>
              <div className="text-severity-3">
                <Sparkline
                  values={alertsSeries.points.map((p) => p.count)}
                  width={320}
                  height={48}
                  ariaLabel="Alerts per day"
                />
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
      {!loaded ? (
        <p className="text-md-sys-color-on-surface-variant">Loading…</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
          {(editing ? orderedWidgets : visibleWidgets).map((w, i, arr) => {
            const hidden = layout.hidden.includes(w.id);
            let value: number;
            try {
              value = w.derive(responses[w.path]);
            } catch {
              value = 0;
            }
            const toneClass =
              w.tone === "alert"
                ? "text-severity-4"
                : w.tone === "warn"
                  ? "text-severity-3"
                  : "";
            return (
              <div
                key={w.id}
                className={
                  "rounded border bg-md-sys-color-surface p-4 " +
                  (hidden && editing
                    ? "border-dashed border-md-sys-color-outline-variant/40 opacity-50"
                    : "border-md-sys-color-outline-variant")
                }
              >
                <div className={"text-3xl font-semibold " + toneClass}>{value}</div>
                {w.link && !editing ? (
                  <Link
                    to={w.link}
                    className="block text-xs text-md-sys-color-on-surface-variant hover:underline"
                    title={`Open ${w.title.toLowerCase()}`}
                  >
                    {w.title}
                  </Link>
                ) : (
                  <div className="text-xs text-md-sys-color-on-surface-variant">
                    {w.title}
                  </div>
                )}
                {editing ? (
                  <div className="mt-2 flex items-center gap-1 text-xs">
                    <button
                      type="button"
                      className="rounded border border-md-sys-color-outline-variant px-1 disabled:opacity-30"
                      onClick={() => move(w.id, -1)}
                      disabled={i === 0}
                      aria-label="Move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="rounded border border-md-sys-color-outline-variant px-1 disabled:opacity-30"
                      onClick={() => move(w.id, 1)}
                      disabled={i === arr.length - 1}
                      aria-label="Move down"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="ml-auto rounded border border-md-sys-color-outline-variant px-1"
                      onClick={() => toggleHidden(w.id)}
                    >
                      {hidden ? "Show" : "Hide"}
                    </button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
      <MttrBreakdownPanel />
      <SlowestOpenCasesPanel />
      <PinnedRunbooksPanel />
      <ObservableTypesPanel />
      <ObservableTlpPanel />
      <StageDistributionPanel />
      <AlertStatusPanel />
      <AuditActivityPanel />
      <CasesByAssigneePanel />
    </section>
  );
}
