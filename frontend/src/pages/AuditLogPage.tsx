/**
 * Audit log viewer (Phase 1b).
 * Read + filter by actor/entity/action. viewAudit-gated.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";
import { useUserNames } from "@/lib/useUserNames";

interface AuditRow {
  id: string;
  actor_user_id: string | null;
  organization_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  request_id: string | null;
  ip: string | null;
  created_at: string;
  diff: Record<string, unknown>;
}

export function AuditLogPage() {
  const { apiCall, permissions } = useAuth();
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [entityType, setEntityType] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [active, setActive] = useState<AuditRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ limit: "200" });
    if (entityType) params.set("entity_type", entityType);
    if (actionFilter) params.set("action", actionFilter);
    apiCall<AuditRow[]>(`/v1/audit?${params.toString()}`)
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, entityType, actionFilter]);

  const userNames = useUserNames(rows?.map((r) => r.actor_user_id) ?? []);

  const filtered = useMemo(() => {
    if (!rows) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.action.toLowerCase().includes(q) ||
        r.entity_type.toLowerCase().includes(q) ||
        (r.entity_id?.toLowerCase().includes(q) ?? false) ||
        (r.actor_user_id?.toLowerCase().includes(q) ?? false),
    );
  }, [rows, filter]);

  if (!permissions.has("viewAudit")) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Audit Log</h1>
        <p role="alert">You do not have viewAudit permission.</p>
      </section>
    );
  }

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (rows === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="grid grid-cols-1 gap-4 p-6 md:grid-cols-[1fr_24rem]">
      <article>
        <h1 className="mb-2 text-2xl font-semibold">Audit Log</h1>
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
            placeholder="Local filter (id, action, entity)…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <select
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
          >
            <option value="">All entities</option>
            <option value="case">case</option>
            <option value="alert">alert</option>
            <option value="user">user</option>
            <option value="observable">observable</option>
            <option value="responder">responder</option>
          </select>
          <input
            className="w-40 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
            placeholder="action (e.g. created)"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          />
        </div>
        {filtered.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">No entries.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {filtered.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setActive(r)}
                  className={
                    "block w-full rounded border px-3 py-1 text-left text-xs " +
                    (active?.id === r.id
                      ? "border-md-sys-color-primary bg-md-sys-color-surface-container"
                      : "border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
                  }
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono uppercase">{r.entity_type}</span>
                    <span className="font-medium">{r.action}</span>
                    <span className="ml-auto text-md-sys-color-on-surface-variant">
                      {new Date(r.created_at).toLocaleString()}
                    </span>
                  </div>
                  {r.entity_id ? (
                    <div className="font-mono text-[10px] text-md-sys-color-on-surface-variant">
                      {r.entity_id}
                    </div>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        )}
      </article>
      <aside>
        {active ? (
          <article className="rounded border border-md-sys-color-outline-variant p-3 text-xs">
            <h2 className="mb-2 text-sm font-medium">
              {active.entity_type}.{active.action}
            </h2>
            <dl className="grid grid-cols-[6rem_1fr] gap-1">
              <dt className="text-md-sys-color-on-surface-variant">When</dt>
              <dd>{new Date(active.created_at).toLocaleString()}</dd>
              <dt className="text-md-sys-color-on-surface-variant">Actor</dt>
              <dd>
                {active.actor_user_id
                  ? (userNames[active.actor_user_id] ??
                    active.actor_user_id.slice(0, 8))
                  : "(system)"}
              </dd>
              <dt className="text-md-sys-color-on-surface-variant">Entity</dt>
              <dd className="font-mono">{active.entity_id ?? "—"}</dd>
              {active.ip ? (
                <>
                  <dt className="text-md-sys-color-on-surface-variant">IP</dt>
                  <dd className="font-mono">{active.ip}</dd>
                </>
              ) : null}
              {active.request_id ? (
                <>
                  <dt className="text-md-sys-color-on-surface-variant">Req ID</dt>
                  <dd className="font-mono">{active.request_id}</dd>
                </>
              ) : null}
            </dl>
            {Object.keys(active.diff).length > 0 ? (
              <>
                <p className="mt-2 text-md-sys-color-on-surface-variant">Diff</p>
                <pre className="max-h-64 overflow-auto rounded bg-md-sys-color-surface-container p-2 text-[10px]">
                  {JSON.stringify(active.diff, null, 2)}
                </pre>
              </>
            ) : null}
          </article>
        ) : (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            Select an entry to see its diff.
          </p>
        )}
      </aside>
    </section>
  );
}
