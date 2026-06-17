/**
 * Renders the N slowest open cases from /v1/stats/slowest-open-cases.
 * Self-contained: fetches on mount + when `limit` changes.
 */

import { Link } from "@tanstack/react-router";
import { useContext, useEffect, useState } from "react";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { AuthContext } from "@/lib/auth";

interface SlowestCase {
  id: string;
  number: number;
  title: string;
  severity: number;
  stage: string;
  assignee_id: string | null;
  hours_open: number;
}

interface SlowestCasesResponse {
  cases: SlowestCase[];
}

function formatAge(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} d`;
}

export function SlowestOpenCasesPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<SlowestCasesResponse | null>(null);
  const [limit, setLimit] = useState(10);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<SlowestCasesResponse>(`/v1/stats/slowest-open-cases?limit=${limit}`)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall, limit]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Slowest open cases</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">by age, oldest first</span>
        <select
          className="ml-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-0.5 text-xs"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          title="Number of cases to show"
        >
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={25}>25</option>
        </select>
      </header>
      {data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : data.cases.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No open cases — nice.</p>
      ) : (
        <ul className="divide-y divide-md-sys-color-outline-variant/40">
          {data.cases.map((c) => (
            <li key={c.id} className="flex items-center gap-2 py-1.5 text-sm">
              <Link
                to="/cases/$caseId"
                params={{ caseId: c.id }}
                className="font-mono text-xs text-md-sys-color-primary hover:underline"
              >
                #{c.number}
              </Link>
              <span className="flex-1 truncate text-xs" title={c.title}>
                {c.title}
              </span>
              <SeverityBadge level={c.severity as SeverityLevel} compact />
              <span className="ml-auto shrink-0 text-xs text-md-sys-color-on-surface-variant">
                {formatAge(c.hours_open)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
