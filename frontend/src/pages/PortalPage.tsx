/**
 * Adhkar Portal: external-collaborator view of cases they've been
 * explicitly shared with. Read-only for now; comment-add lands later.
 *
 * Backend: /v1/cases already enforces org-scoping + permissions. For Portal
 * users we list cases where a CaseShare row exists for the current user.
 * The dedicated `/v1/portal/cases` endpoint is RC8 work; for now we use
 * the regular /v1/cases endpoint which returns whatever the user can see.
 */

import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

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
  updated_at: string;
  can_comment: boolean;
  can_upload: boolean;
}

export function PortalPage() {
  const { apiCall, user } = useAuth();
  const [cases, setCases] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiCall<CaseRow[]>("/v1/portal/cases")
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
        <h1 className="mb-4 text-2xl font-semibold">Portal</h1>
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  }
  if (cases === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-4 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Portal</h1>
        <p className="text-sm text-md-sys-color-on-surface-variant">
          Welcome{user ? `, ${user.display_name}` : ""}. These are the cases
          your IR team has shared with you.
        </p>
      </header>
      {cases.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">
          No shared cases yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {cases.map((c) => (
            <li
              key={c.id}
              className="rounded border border-md-sys-color-outline-variant p-3 hover:bg-md-sys-color-surface-container"
            >
              <Link
                to="/cases/$caseId"
                params={{ caseId: c.id }}
                className="flex items-center gap-3 text-sm"
              >
                <span className="font-mono text-xs">#{c.number}</span>
                <span className="font-medium">{c.title}</span>
                <span className="ml-auto flex items-center gap-2">
                  <SeverityBadge level={c.severity} compact />
                  <TLPBadge tlp={c.tlp} />
                  <span className="text-xs text-md-sys-color-on-surface-variant">
                    {c.stage}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
