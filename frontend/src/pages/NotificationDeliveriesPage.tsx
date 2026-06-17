/**
 * Notification delivery log (RC80). Lists GET /v1/notification-deliveries.
 * manageConfig-gated.
 */

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface DeliveryDTO {
  id: string;
  rule_id: string | null;
  endpoint_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  status: "pending" | "succeeded" | "failed";
  attempts: number;
  last_error: string | null;
  created_at: string;
  delivered_at: string | null;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function StatusChip({ status }: { status: DeliveryDTO["status"] }) {
  const cls =
    status === "succeeded"
      ? "bg-tlp-green/20 text-tlp-green"
      : status === "failed"
        ? "bg-severity-3/20 text-severity-3"
        : "bg-md-sys-color-surface-container text-md-sys-color-on-surface-variant";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${cls}`}>
      {status}
    </span>
  );
}

export function NotificationDeliveriesPage() {
  const { apiCall, permissions } = useAuth();

  const [rows, setRows] = useState<DeliveryDTO[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<"" | "pending" | "succeeded" | "failed">("");
  const [ruleId, setRuleId] = useState("");
  const [endpointId, setEndpointId] = useState("");

  const hasFilters = statusFilter !== "" || ruleId.trim() !== "" || endpointId.trim() !== "";

  const fetch = useCallback(() => {
    setRows(null);
    setError(null);
    const params = new URLSearchParams({ limit: "200" });
    if (statusFilter) params.set("status_filter", statusFilter);
    if (ruleId.trim()) params.set("rule_id", ruleId.trim());
    if (endpointId.trim()) params.set("endpoint_id", endpointId.trim());
    apiCall<DeliveryDTO[]>(`/v1/notification-deliveries?${params.toString()}`)
      .then((r) => setRows(r))
      .catch((e: Error) => setError(e.message));
  }, [apiCall, statusFilter, ruleId, endpointId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  function reset() {
    setStatusFilter("");
    setRuleId("");
    setEndpointId("");
  }

  if (!permissions.has("manageConfig")) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Notification deliveries</h1>
        <p role="alert">You do not have manageConfig permission.</p>
      </section>
    );
  }

  return (
    <section className="space-y-4 p-6">
      <div className="flex items-center gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Notification deliveries</h1>
          <p className="text-sm text-md-sys-color-on-surface-variant">
            {rows === null ? "Loading…" : `${rows.length} row${rows.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <button
          type="button"
          onClick={fetch}
          className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
        >
          Refresh
        </button>
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-2">
        <select
          className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          value={statusFilter}
          onChange={(e) =>
            setStatusFilter(e.target.value as "" | "pending" | "succeeded" | "failed")
          }
        >
          <option value="">All statuses</option>
          <option value="pending">pending</option>
          <option value="succeeded">succeeded</option>
          <option value="failed">failed</option>
        </select>
        <input
          className="w-52 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 font-mono text-sm"
          placeholder="rule_id (UUID)"
          value={ruleId}
          onChange={(e) => setRuleId(e.target.value)}
        />
        <input
          className="w-52 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 font-mono text-sm"
          placeholder="endpoint_id (UUID)"
          value={endpointId}
          onChange={(e) => setEndpointId(e.target.value)}
        />
        {hasFilters ? (
          <button
            type="button"
            onClick={reset}
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
          >
            Reset
          </button>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-sm text-severity-4">
          {error}
        </p>
      ) : rows === null ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">
          No deliveries match these filters.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-md-sys-color-outline-variant text-left text-xs text-md-sys-color-on-surface-variant">
                <th className="py-2 pr-3 font-medium">When</th>
                <th className="py-2 pr-3 font-medium">Event type</th>
                <th className="py-2 pr-3 font-medium">Rule</th>
                <th className="py-2 pr-3 font-medium">Endpoint</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Attempts</th>
                <th className="py-2 pr-3 font-medium">Last error</th>
                <th className="py-2 font-medium">Delivered</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-md-sys-color-outline-variant/50 hover:bg-md-sys-color-surface-container"
                >
                  <td className="py-1.5 pr-3 text-xs">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-xs">{row.event_type}</td>
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {row.rule_id ? row.rule_id.slice(0, 8) : "—"}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {row.endpoint_id ? row.endpoint_id.slice(0, 8) : "—"}
                  </td>
                  <td className="py-1.5 pr-3">
                    <StatusChip status={row.status} />
                  </td>
                  <td className="py-1.5 pr-3 text-xs">{row.attempts}</td>
                  <td className="max-w-[12rem] py-1.5 pr-3 text-xs">
                    {row.last_error ? (
                      <span
                        title={row.last_error}
                        className="block truncate text-md-sys-color-on-surface-variant"
                      >
                        {row.last_error.length > 80
                          ? row.last_error.slice(0, 80) + "…"
                          : row.last_error}
                      </span>
                    ) : (
                      <span className="text-md-sys-color-on-surface-variant">—</span>
                    )}
                  </td>
                  <td className="py-1.5 text-xs text-md-sys-color-on-surface-variant">
                    {row.delivered_at ? relativeTime(row.delivered_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
