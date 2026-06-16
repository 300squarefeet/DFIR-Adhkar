/**
 * Knowledge Base list (Phase 6). Read + view-by-slug.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";

interface KbPage {
  id: string;
  slug: string;
  title: string;
  content: string;
  tags: string[];
  updated_at: string;
}

export function KnowledgeBasePage() {
  const { apiCall } = useAuth();
  const [pages, setPages] = useState<KbPage[] | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiCall<KbPage[]>("/v1/kb/pages")
      .then((p) => {
        if (!cancelled) setPages(p);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  const filtered = useMemo(() => {
    if (!pages) return [];
    if (!filter.trim()) return pages;
    const q = filter.trim().toLowerCase();
    return pages.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q) ||
        p.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [pages, filter]);

  const active = pages?.find((p) => p.slug === activeSlug) ?? null;

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (pages === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="grid grid-cols-1 gap-4 p-6 md:grid-cols-[16rem_1fr]">
      <aside>
        <h1 className="mb-2 text-xl font-semibold">Knowledge Base</h1>
        <input
          className="mb-3 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {filtered.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">No pages.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {filtered.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setActiveSlug(p.slug)}
                  className={
                    "block w-full truncate rounded px-2 py-1 text-left hover:bg-md-sys-color-surface-container " +
                    (p.slug === activeSlug ? "bg-md-sys-color-surface-container" : "")
                  }
                >
                  {p.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <article>
        {active ? (
          <>
            <header className="mb-2">
              <h2 className="text-2xl font-semibold">{active.title}</h2>
              <p className="text-xs text-md-sys-color-on-surface-variant">
                {active.slug} · updated {new Date(active.updated_at).toLocaleString()}
              </p>
            </header>
            <pre className="whitespace-pre-wrap rounded border border-md-sys-color-outline-variant p-3 text-sm">
              {active.content}
            </pre>
          </>
        ) : (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            Select a page from the left.
          </p>
        )}
      </article>
    </section>
  );
}
