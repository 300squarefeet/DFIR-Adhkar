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

export function AdminProfilesPage() {
  const { apiCall } = useAuth();
  const [profiles, setProfiles] = useState<ProfileRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiCall<ProfileRow[]>("/v1/profiles")
      .then((p) => {
        if (!cancelled) setProfiles(p);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (profiles === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Profiles (RBAC)</h1>
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
