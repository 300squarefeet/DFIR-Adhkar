/**
 * Cases list (Phase 3). Read-only first cut: lists cases for the active org
 * and shows number/title/severity/TLP/stage/updated. Create/edit lands later.
 */

import { useEffect, useState } from "react";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

interface CaseRow {
  id: string;
  number: number;
  title: string;
  severity: SeverityLevel;
  tlp: TLPValue;
  stage: string;
  status: string;
  tags: string[];
  assignee_id: string | null;
  updated_at: string;
}

export function CasesPage() {
  const { apiCall } = useAuth();
  const [cases, setCases] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiCall<CaseRow[]>("/v1/cases")
      .then((rows) => {
        if (!cancelled) setCases(rows);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (error) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Cases</h1>
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          Failed to load cases: {error}
        </p>
      </section>
    );
  }

  if (cases === null) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Cases</h1>
        <p className="text-md-sys-color-on-surface-variant">Loading…</p>
      </section>
    );
  }

  if (cases.length === 0) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Cases</h1>
        <p className="text-md-sys-color-on-surface-variant">
          No cases yet for this organization.
        </p>
      </section>
    );
  }

  return (
    <section className="p-6">
      <h1 className="mb-4 text-2xl font-semibold">Cases</h1>
      <table className="w-full table-auto border-collapse text-sm">
        <thead>
          <tr className="border-b border-md-sys-color-outline-variant text-left">
            <th className="py-2 pr-3">#</th>
            <th className="py-2 pr-3">Title</th>
            <th className="py-2 pr-3">Severity</th>
            <th className="py-2 pr-3">TLP</th>
            <th className="py-2 pr-3">Stage</th>
            <th className="py-2 pr-3">Updated</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr
              key={c.id}
              className="border-b border-md-sys-color-outline-variant/50 hover:bg-md-sys-color-surface-container"
            >
              <td className="py-2 pr-3 font-mono">#{c.number}</td>
              <td className="py-2 pr-3">{c.title}</td>
              <td className="py-2 pr-3">
                <SeverityBadge level={c.severity} compact />
              </td>
              <td className="py-2 pr-3">
                <TLPBadge tlp={c.tlp} />
              </td>
              <td className="py-2 pr-3">{c.stage}</td>
              <td className="py-2 pr-3 text-md-sys-color-on-surface-variant">
                {new Date(c.updated_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
