/**
 * Renders the 10 most-recently-updated KB pages from
 * /v1/kb/pages/recent?limit=10.
 * Self-contained: fetches once on mount.
 */

import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface RecentKbPage {
  id: string;
  slug: string;
  title: string;
  pinned: boolean;
  updated_at: string;
}

function formatAge(deltaMs: number): string {
  const minutes = deltaMs / 60_000;
  const hours = minutes / 60;
  if (hours < 1) return `${Math.round(minutes)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export function RecentKbPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [data, setData] = useState<RecentKbPage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<RecentKbPage[]>("/v1/kb/pages/recent?limit=10")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error).message ?? "Failed to load recent runbooks.");
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Recently edited runbooks</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">knowledge base, last updated</span>
      </header>
      {error !== null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">{error}</p>
      ) : data === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No runbooks yet.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.map((p) => (
            <li key={p.id} className="flex items-center gap-2">
              <a href={`/knowledge-base?slug=${encodeURIComponent(p.slug)}`} className="hover:underline">
                <span className="font-mono text-xs mr-2">{p.slug}</span>
                <span className="truncate">{p.title}</span>
              </a>
              <div className="ml-auto flex shrink-0 items-center gap-2">
                {p.pinned ? (
                  <span className="text-md-sys-color-primary">⚲</span>
                ) : null}
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  updated {formatAge(Date.now() - new Date(p.updated_at).getTime())}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
