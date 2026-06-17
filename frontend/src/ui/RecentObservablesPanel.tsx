/**
 * Renders the 10 most-recently-updated confirmed IOCs from
 * /v1/observables/recent?limit=10&is_ioc=true.
 * Self-contained: fetches once on mount.
 */

import { useContext, useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { AuthContext } from "@/lib/auth";

interface RecentObservable {
  id: string;
  data_type: string;
  data: string;
  updated_at: string;
}

const DATA_TYPES = ["ip", "domain", "url", "hash", "email", "filename"];

function formatAge(deltaMs: number): string {
  const minutes = deltaMs / 60_000;
  const hours = minutes / 60;
  if (hours < 1) return `${Math.round(minutes)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export function RecentObservablesPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<RecentObservable[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dataTypeFilter, setDataTypeFilter] = useState<string>("");

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    const url =
      dataTypeFilter === ""
        ? "/v1/observables/recent?limit=10&is_ioc=true"
        : `/v1/observables/recent?limit=10&is_ioc=true&data_type=${encodeURIComponent(dataTypeFilter)}`;
    apiCall<RecentObservable[]>(url)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error).message ?? "Failed to load recent IOCs.");
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, dataTypeFilter]);

  if (!apiCall) return null;

  const chipBase = "rounded-full px-2 py-0.5 text-xs";
  const chipActive = "bg-md-sys-color-primary text-md-sys-color-on-primary";
  const chipInactive =
    "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container";

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <h2 className="font-medium">Recent IOCs</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">confirmed IOCs, last updated</span>
        <div className="ml-auto flex flex-wrap items-center gap-1">
          <button
            type="button"
            onClick={() => setDataTypeFilter("")}
            className={`${chipBase} ${dataTypeFilter === "" ? chipActive : chipInactive}`}
          >
            All
          </button>
          {DATA_TYPES.map((dt) => (
            <button
              key={dt}
              type="button"
              onClick={() => setDataTypeFilter(dt)}
              className={`${chipBase} ${dataTypeFilter === dt ? chipActive : chipInactive}`}
            >
              {dt}
            </button>
          ))}
        </div>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No recent IOCs.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.map((o) => (
            <li key={o.id} className="flex items-center gap-2">
              <Link
                to="/observables/$observableId"
                params={{ observableId: o.id }}
                className="font-mono hover:underline"
              >
                {o.data_type}
              </Link>
              <span className="truncate font-mono">{o.data}</span>
              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  updated {formatAge(Date.now() - new Date(o.updated_at).getTime())}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
