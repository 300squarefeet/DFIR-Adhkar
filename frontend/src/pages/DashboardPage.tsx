/**
 * Dashboard (Phase 6) — widget-driven. Each WidgetSpec declares its own
 * endpoint and how to derive its KPI; results are deduped per endpoint so
 * we don't refetch the same list multiple times.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";
import { CORE_WIDGETS, type WidgetSpec } from "@/ui/widgets";

export function DashboardPage() {
  const { apiCall } = useAuth();
  const [responses, setResponses] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);

  const uniquePaths = useMemo(() => {
    const set = new Set<string>();
    for (const w of CORE_WIDGETS) set.add(w.path);
    return Array.from(set);
  }, []);

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
      <h1 className="mb-4 text-2xl font-semibold">Dashboard</h1>
      {!loaded ? (
        <p className="text-md-sys-color-on-surface-variant">Loading…</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
          {CORE_WIDGETS.map((w: WidgetSpec) => {
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
                className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-4"
              >
                <div className={"text-3xl font-semibold " + toneClass}>{value}</div>
                <div className="text-xs text-md-sys-color-on-surface-variant">
                  {w.title}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
