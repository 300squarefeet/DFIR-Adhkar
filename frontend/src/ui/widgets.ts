/**
 * Dashboard widget engine: small declarative API where each widget
 * declares its API call + how to derive a number/series from the response.
 * Phase 6 final cut. Drag-and-drop layout lands in Phase 6c.
 */

export interface WidgetSpec {
  id: string;
  title: string;
  /** Backend path to fetch */
  path: string;
  /** Derive a single KPI number from the response */
  derive: (rows: unknown) => number;
  tone?: "default" | "warn" | "alert";
}

interface Severityish {
  severity?: number;
  stage?: string;
  status?: string;
}

function asArray<T>(x: unknown): T[] {
  return Array.isArray(x) ? (x as T[]) : [];
}

export const CORE_WIDGETS: ReadonlyArray<WidgetSpec> = [
  {
    id: "open-cases",
    title: "Open cases",
    path: "/v1/cases?limit=500",
    derive: (r) => asArray<Severityish>(r).filter((c) => c.stage !== "closed").length,
  },
  {
    id: "critical-cases",
    title: "Critical (sev 4)",
    path: "/v1/cases?limit=500",
    derive: (r) =>
      asArray<Severityish>(r).filter((c) => c.severity === 4 && c.stage !== "closed").length,
    tone: "alert",
  },
  {
    id: "high-cases",
    title: "High severity (sev ≥3)",
    path: "/v1/cases?limit=500",
    derive: (r) =>
      asArray<Severityish>(r).filter(
        (c) => (c.severity ?? 0) >= 3 && c.stage !== "closed",
      ).length,
    tone: "warn",
  },
  {
    id: "closed-cases",
    title: "Closed cases",
    path: "/v1/cases?limit=500",
    derive: (r) => asArray<Severityish>(r).filter((c) => c.stage === "closed").length,
  },
  {
    id: "new-alerts",
    title: "New/updated alerts",
    path: "/v1/alerts?limit=500",
    derive: (r) =>
      asArray<Severityish>(r).filter(
        (a) => a.status === "New" || a.status === "Updated",
      ).length,
    tone: "warn",
  },
  {
    id: "imported-alerts",
    title: "Imported alerts",
    path: "/v1/alerts?limit=500",
    derive: (r) => asArray<Severityish>(r).filter((a) => a.status === "Imported").length,
  },
  {
    id: "iocs",
    title: "Confirmed IOCs",
    path: "/v1/observables?limit=500",
    derive: (r) => asArray<{ is_ioc?: boolean }>(r).filter((o) => Boolean(o.is_ioc)).length,
    tone: "warn",
  },
];
