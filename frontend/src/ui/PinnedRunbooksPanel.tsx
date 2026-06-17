/**
 * Renders the pinned KB pages from /v1/kb/pages?pinned_only=true as a list
 * so analysts can jump straight to a runbook from the dashboard.
 * Self-contained: fetches on mount. Null-safe useContext(AuthContext) so
 * AppShell tests (no AuthProvider) stay green.
 */

import { Link } from "@tanstack/react-router";
import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface PinnedPage {
  id: string;
  slug: string;
  title: string;
  pinned: boolean;
}

export function PinnedRunbooksPanel() {
  const ctx = useContext(AuthContext);
  const apiCall = ctx?.apiCall;
  const [pages, setPages] = useState<PinnedPage[] | null>(null);

  useEffect(() => {
    if (!apiCall) return;
    let cancelled = false;
    apiCall<PinnedPage[]>("/v1/kb/pages?pinned_only=true&limit=20")
      .then((r) => {
        if (!cancelled) setPages(r);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  if (!apiCall) return null;

  return (
    <article className="mb-4 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-3">
      <header className="mb-2 flex items-center gap-2 text-sm">
        <h2 className="font-medium">Pinned runbooks</h2>
        <span className="text-xs text-md-sys-color-on-surface-variant">
          click to open
        </span>
        <Link
          to="/knowledge-base"
          className="ml-auto text-xs text-md-sys-color-primary hover:underline"
        >
          Open KB →
        </Link>
      </header>
      {pages === null ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">Loading…</p>
      ) : pages.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">
          No pinned runbooks yet — pin one from the Knowledge Base.
        </p>
      ) : (
        <ul className="space-y-1 text-sm">
          {pages.map((page) => (
            <li key={page.id}>
              <Link
                to="/knowledge-base"
                className="flex items-center gap-1.5 hover:underline"
              >
                <span className="text-md-sys-color-primary">⚲</span>
                <span className="truncate">{page.title}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
