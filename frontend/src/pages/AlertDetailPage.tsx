/**
 * Alert detail (Phase 4).
 * Read-only view + status patch + promote-to-case button.
 */

import { useEffect, useState } from "react";

import { useRouter } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface AlertDetail {
  id: string;
  type: string;
  source: string;
  source_ref: string;
  title: string;
  description: string | null;
  severity: SeverityLevel;
  tlp: TLPValue;
  pap: string;
  status: string;
  tags: string[];
  custom_fields: Record<string, unknown>;
  case_id: string | null;
  imported_at: string | null;
  created_at: string;
  updated_at: string;
}

interface Props {
  alertId: string;
}

interface TimelineEntry {
  id: string;
  action: string;
  entity_type: string;
  actor_user_id: string | null;
  created_at: string;
}

const STATUSES = ["New", "Updated", "Ignored", "Imported"] as const;

export function AlertDetailPage({ alertId }: Props) {
  const { apiCall, permissions } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a, tl] = await Promise.all([
          apiCall<AlertDetail>(`/v1/alerts/${alertId}`),
          apiCall<{ entries: TimelineEntry[] }>(
            `/v1/alerts/${alertId}/timeline?limit=100`,
          ).catch(() => ({ entries: [] as TimelineEntry[] })),
        ]);
        if (cancelled) return;
        setAlert(a);
        setTimeline(tl.entries);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, alertId]);

  const setStatus = async (status: string) => {
    if (!alert) return;
    setBusy(true);
    try {
      const updated = await apiCall<AlertDetail>(`/v1/alerts/${alertId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setAlert(updated);
      toast.success(`Status set to ${status}.`);
    } catch (e) {
      setError((e as Error).message);
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const promote = async () => {
    if (!alert) return;
    setBusy(true);
    try {
      const r = await apiCall<{ case_id: string; case_number: number }>(
        `/v1/alerts/${alertId}/promote`,
        { method: "POST", body: "{}" },
      );
      toast.success(`Promoted to case #${r.case_number}.`);
      await router.navigate({ to: "/cases/$caseId", params: { caseId: r.case_id } });
    } catch (e) {
      setError((e as Error).message);
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (!alert) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-4 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-md-sys-color-on-surface-variant">
            {alert.source}/{alert.source_ref}
          </span>
          <h1 className="text-2xl font-semibold">{alert.title}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge level={alert.severity} />
          <TLPBadge tlp={alert.tlp} />
          <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-xs">
            {alert.status}
          </span>
          {alert.case_id ? (
            <span className="text-xs text-tlp-green">
              promoted → case {alert.case_id.slice(0, 8)}
            </span>
          ) : null}
          {alert.tags.map((t) => (
            <span
              key={t}
              className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs"
            >
              #{t}
            </span>
          ))}
        </div>
        {alert.description ? (
          <p className="whitespace-pre-wrap text-sm">{alert.description}</p>
        ) : null}
      </header>

      {permissions.has("manageAlert") && alert.case_id === null ? (
        <article className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-md-sys-color-on-surface-variant">Status:</span>
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              disabled={busy || alert.status === s}
              className={
                "rounded-full px-3 py-0.5 text-xs disabled:opacity-50 " +
                (alert.status === s
                  ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                  : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
              }
              onClick={() => {
                void setStatus(s);
              }}
            >
              {s}
            </button>
          ))}
          {permissions.has("manageCase") ? (
            <button
              type="button"
              disabled={busy}
              className="ml-auto rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void promote();
              }}
            >
              {busy ? "…" : "Promote → Case"}
            </button>
          ) : null}
        </article>
      ) : null}

      <article>
        <h2 className="mb-2 text-sm font-medium">Timeline ({timeline.length})</h2>
        {timeline.length === 0 ? (
          <p className="text-xs text-md-sys-color-on-surface-variant">No audit events.</p>
        ) : (
          <ol className="space-y-1 text-xs">
            {timeline.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-2 rounded border border-md-sys-color-outline-variant/50 px-3 py-1"
              >
                <span className="font-mono uppercase">{t.entity_type}</span>
                <span className="font-medium">{t.action}</span>
                <span className="ml-auto text-md-sys-color-on-surface-variant">
                  {new Date(t.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ol>
        )}
      </article>

      {Object.keys(alert.custom_fields).length > 0 ? (
        <article>
          <h2 className="mb-2 text-sm font-medium">Custom fields</h2>
          <pre className="rounded border border-md-sys-color-outline-variant p-2 text-xs">
            {JSON.stringify(alert.custom_fields, null, 2)}
          </pre>
        </article>
      ) : null}
    </section>
  );
}
