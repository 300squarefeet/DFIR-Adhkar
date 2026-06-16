/**
 * Dashboard (Phase 6 stub): KPIs derived client-side from cases + alerts.
 * Phase 6b will swap to dashboard-widget engine.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface CaseRow {
  id: string;
  severity: 1 | 2 | 3 | 4;
  stage: string;
  status: string;
}

interface AlertRow {
  id: string;
  status: string;
}

interface Kpi {
  label: string;
  value: number;
  tone?: "default" | "warn" | "alert";
}

export function DashboardPage() {
  const { apiCall } = useAuth();
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [c, a] = await Promise.all([
          apiCall<CaseRow[]>("/v1/cases?limit=500"),
          apiCall<AlertRow[]>("/v1/alerts?limit=500"),
        ]);
        if (cancelled) return;
        setCases(c);
        setAlerts(a);
        setLoaded(true);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  const kpis: Kpi[] = [
    { label: "Open cases", value: cases.filter((c) => c.stage !== "closed").length },
    {
      label: "Critical cases (sev 4)",
      value: cases.filter((c) => c.severity === 4 && c.stage !== "closed").length,
      tone: "alert",
    },
    {
      label: "High severity (sev 3+)",
      value: cases.filter((c) => c.severity >= 3 && c.stage !== "closed").length,
      tone: "warn",
    },
    { label: "Closed cases", value: cases.filter((c) => c.stage === "closed").length },
    {
      label: "New alerts",
      value: alerts.filter((a) => a.status === "New" || a.status === "Updated").length,
      tone: "warn",
    },
    {
      label: "Imported alerts",
      value: alerts.filter((a) => a.status === "Imported").length,
    },
  ];

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );

  return (
    <section className="p-6">
      <h1 className="mb-4 text-2xl font-semibold">Dashboard</h1>
      {!loaded ? (
        <p className="text-md-sys-color-on-surface-variant">Loading…</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {kpis.map((k) => (
            <div
              key={k.label}
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-4"
            >
              <div
                className={
                  "text-3xl font-semibold " +
                  (k.tone === "alert"
                    ? "text-severity-4"
                    : k.tone === "warn"
                      ? "text-severity-3"
                      : "")
                }
              >
                {k.value}
              </div>
              <div className="text-xs text-md-sys-color-on-surface-variant">{k.label}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
