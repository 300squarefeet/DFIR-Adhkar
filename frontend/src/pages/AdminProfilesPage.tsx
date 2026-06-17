/**
 * Admin: Profiles (RBAC) viewer (Phase 1a UI gap).
 * Read-only first cut. Editor lands later.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface ProfileRow {
  id: string;
  name: string;
  permissions: string[];
  is_default: boolean;
}

const PERMISSION_FILTERS = [
  "manageCase",
  "manageUser",
  "manageConfig",
  "viewAudit",
  "auditExport",
  "gdprAccess",
] as const;

export function AdminProfilesPage() {
  const { apiCall } = useAuth();
  const [profiles, setProfiles] = useState<ProfileRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permFilter, setPermFilter] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    const url = permFilter
      ? `/v1/profiles?with_permission=${permFilter}`
      : "/v1/profiles";
    apiCall<ProfileRow[]>(url)
      .then((p) => {
        if (!cancelled) setProfiles(p);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, permFilter]);

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (profiles === null) return <section className="p-6">Loading…</section>;

  const chipBase = "rounded-full px-2 py-0.5 text-xs";
  const chipActive = "bg-md-sys-color-primary text-md-sys-color-on-primary";
  const chipInactive =
    "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container";

  return (
    <section className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Profiles (RBAC)</h1>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-md-sys-color-on-surface-variant">
          Has permission:
        </span>
        <button
          type="button"
          aria-pressed={permFilter === ""}
          onClick={() => setPermFilter("")}
          className={`${chipBase} ${permFilter === "" ? chipActive : chipInactive}`}
        >
          Any
        </button>
        {PERMISSION_FILTERS.map((key) => {
          const active = permFilter === key;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={active}
              onClick={() => setPermFilter(key)}
              className={`${chipBase} ${active ? chipActive : chipInactive}`}
            >
              {key}
            </button>
          );
        })}
      </div>
      {profiles.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">No profiles.</p>
      ) : (
        <ul className="space-y-3">
          {profiles.map((p) => (
            <li
              key={p.id}
              className="rounded border border-md-sys-color-outline-variant p-3"
            >
              <div className="flex items-center gap-2">
                <h2 className="font-medium">{p.name}</h2>
                {p.is_default ? (
                  <span className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs">
                    default
                  </span>
                ) : null}
                <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                  {p.permissions.length} permissions
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {p.permissions.map((perm) => (
                  <span
                    key={perm}
                    className="rounded bg-md-sys-color-surface-container px-1.5 py-0.5 font-mono text-[10px]"
                  >
                    {perm}
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
