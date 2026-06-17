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
  /** Optional UI deep-link to a list page that matches the same filter. */
  link?: string;
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
    link: "/cases",
  },
  {
    id: "critical-cases",
    title: "Critical (sev 4)",
    path: "/v1/cases?limit=500",
    derive: (r) =>
      asArray<Severityish>(r).filter((c) => c.severity === 4 && c.stage !== "closed").length,
    tone: "alert",
    link: "/cases",
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
    link: "/cases",
  },
  {
    id: "closed-cases",
    title: "Closed cases",
    path: "/v1/cases?limit=500",
    derive: (r) => asArray<Severityish>(r).filter((c) => c.stage === "closed").length,
    link: "/cases",
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
    link: "/alerts",
  },
  {
    id: "imported-alerts",
    title: "Imported alerts",
    path: "/v1/alerts?limit=500",
    derive: (r) => asArray<Severityish>(r).filter((a) => a.status === "Imported").length,
    link: "/alerts",
  },
  {
    id: "iocs",
    title: "Confirmed IOCs",
    path: "/v1/observables?limit=500",
    derive: (r) => asArray<{ is_ioc?: boolean }>(r).filter((o) => Boolean(o.is_ioc)).length,
    tone: "warn",
    link: "/observables",
  },
  {
    id: "flagged-cases",
    title: "Flagged cases",
    path: "/v1/cases?flagged=true&limit=500",
    derive: (r) => asArray<unknown>(r).length,
    tone: "alert",
    link: "/cases",
  },
  {
    id: "unpromoted-alerts",
    title: "Unpromoted alerts",
    path: "/v1/alerts?unpromoted=true&limit=500",
    derive: (r) => asArray<unknown>(r).length,
    tone: "warn",
    link: "/alerts",
  },
  {
    id: "overdue-tasks",
    title: "Overdue tasks",
    path: "/v1/tasks?overdue=true&limit=500",
    derive: (r) => asArray<unknown>(r).length,
    tone: "alert",
    link: "/tasks",
  },
  {
    id: "my-open-tasks",
    title: "My open tasks",
    path: "/v1/tasks?mine=true&limit=500",
    derive: (r) =>
      asArray<{ status?: string }>(r).filter(
        (t) => t.status !== "Completed" && t.status !== "Cancelled",
      ).length,
    link: "/tasks",
  },
  {
    id: "my-mentions-unread",
    title: "My unread mentions",
    path: "/v1/mentions/me/unread",
    derive: (r) =>
      typeof r === "object" && r !== null && "unread" in r
        ? Number((r as { unread?: unknown }).unread ?? 0)
        : 0,
    tone: "warn",
    link: "/mentions",
  },
  {
    id: "sighted-observables",
    title: "Sighted observables",
    path: "/v1/observables?sighted=true&limit=500",
    derive: (r) => asArray<unknown>(r).length,
    link: "/observables",
  },
  {
    id: "pinned-kb",
    title: "Pinned runbooks",
    path: "/v1/kb/pages?pinned_only=true&limit=200",
    derive: (r) => asArray<unknown>(r).length,
    link: "/knowledge-base",
  },
  {
    id: "failed-deliveries",
    title: "Failed deliveries",
    path: "/v1/notification-deliveries?status_filter=failed&limit=500",
    derive: (r) => asArray<unknown>(r).length,
    tone: "alert",
    link: "/admin/notification-deliveries",
  },
  {
    id: "mttr-30d-hours",
    title: "Median MTTR 30d (h)",
    path: "/v1/stats/case-mttr?days=30",
    derive: (r) => {
      if (typeof r !== "object" || r === null || !("buckets" in r)) return 0;
      const buckets = (r as { buckets?: { median_hours?: number | null; closed_count?: number }[] })
        .buckets;
      if (!Array.isArray(buckets)) return 0;
      const all: number[] = [];
      for (const b of buckets) {
        if (typeof b.median_hours === "number" && b.closed_count) {
          for (let i = 0; i < b.closed_count; i++) all.push(b.median_hours);
        }
      }
      if (all.length === 0) return 0;
      all.sort((a, b) => a - b);
      const mid = all.length >> 1;
      const m =
        all.length % 2 === 1
          ? (all[mid] ?? 0)
          : ((all[mid - 1] ?? 0) + (all[mid] ?? 0)) / 2;
      return Math.round(m);
    },
  },
];
