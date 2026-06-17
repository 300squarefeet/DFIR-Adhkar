/**
 * Knowledge Base list (Phase 6). Read + view-by-slug.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface KbPage {
  id: string;
  slug: string;
  title: string;
  content: string;
  tags: string[];
  pinned: boolean;
  updated_at: string;
}

export function KnowledgeBasePage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const urlOverride = (() => {
    if (typeof window === "undefined") return {} as Partial<{ tag: string; slug: string; q: string }>;
    const params = new URLSearchParams(window.location.search);
    const result: Partial<{ tag: string; slug: string; q: string }> = {};
    const tag = params.get("tag");
    if (tag) result.tag = tag;
    const slug = params.get("slug");
    if (slug) result.slug = slug;
    const q = params.get("q");
    if (q) result.q = q;
    return result;
  })();

  const [pages, setPages] = useState<KbPage[] | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(urlOverride.slug ?? null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState(urlOverride.q ?? "");
  const [editing, setEditing] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editedWithin, setEditedWithin] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    const url =
      editedWithin >= 1
        ? `/v1/kb/pages?updated_since=${encodeURIComponent(
            new Date(Date.now() - editedWithin * 3600 * 1000).toISOString(),
          )}`
        : "/v1/kb/pages";
    apiCall<KbPage[]>(url)
      .then((p) => {
        if (!cancelled) setPages(p);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, editedWithin]);

  const allTags = useMemo(() => {
    if (!pages) return [] as string[];
    return Array.from(new Set(pages.flatMap((p) => p.tags))).sort();
  }, [pages]);

  const [activeTag, setActiveTag] = useState<string>(urlOverride.tag ?? "");

  const filtered = useMemo(() => {
    if (!pages) return [];
    let out = pages;
    if (activeTag) out = out.filter((p) => p.tags.includes(activeTag));
    const q = filter.trim().toLowerCase();
    if (!q) return out;
    return out.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q) ||
        p.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [pages, filter, activeTag]);

  const active = pages?.find((p) => p.slug === activeSlug) ?? null;
  const canManage = permissions.has("manageConfig");

  const refresh = async () => {
    try {
      const p = await apiCall<KbPage[]>("/v1/kb/pages");
      setPages(p);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const [draftTags, setDraftTags] = useState("");

  const togglePin = async (p: KbPage) => {
    try {
      const updated = await apiCall<KbPage>(`/v1/kb/pages/${p.id}`, {
        method: "PATCH",
        body: JSON.stringify({ pinned: !p.pinned }),
      });
      setPages((prev) =>
        prev ? prev.map((x) => (x.id === updated.id ? updated : x)) : prev,
      );
      toast.success(updated.pinned ? "Pinned." : "Unpinned.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const saveEdit = async () => {
    if (!active) return;
    const tags = draftTags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      const updated = await apiCall<KbPage>(`/v1/kb/pages/${active.id}`, {
        method: "PATCH",
        body: JSON.stringify({ content: draftContent, tags }),
      });
      setPages((prev) =>
        prev ? prev.map((p) => (p.id === updated.id ? updated : p)) : prev,
      );
      setEditing(false);
      toast.success("Page saved.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const createPage = async () => {
    if (!newSlug.trim() || !newTitle.trim()) return;
    try {
      const created = await apiCall<KbPage>("/v1/kb/pages", {
        method: "POST",
        body: JSON.stringify({
          slug: newSlug.trim(),
          title: newTitle.trim(),
          content: "",
        }),
      });
      await refresh();
      setActiveSlug(created.slug);
      setNewSlug("");
      setNewTitle("");
      setShowCreate(false);
      toast.success("Page created.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  useEffect(() => {
    if (active) {
      setDraftContent(active.content);
      setDraftTags(active.tags.join(", "));
    }
  }, [active]);

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
        <div className="mb-2 flex items-center gap-2">
          <h1 className="text-xl font-semibold">Knowledge Base</h1>
          {canManage ? (
            <button
              type="button"
              className="ml-auto rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
              onClick={() => setShowCreate((v) => !v)}
            >
              {showCreate ? "Cancel" : "+ Page"}
            </button>
          ) : null}
        </div>
        {showCreate && canManage ? (
          <div className="mb-3 space-y-1 rounded border border-md-sys-color-outline-variant p-2">
            <input
              className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
              placeholder="slug (lowercase-hyphens)"
              value={newSlug}
              onChange={(e) => setNewSlug(e.target.value)}
            />
            <input
              className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
              placeholder="Title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <button
              type="button"
              className="w-full rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void createPage();
              }}
              disabled={!newSlug.trim() || !newTitle.trim()}
            >
              Create
            </button>
          </div>
        ) : null}
        <div className="mb-3 flex flex-wrap items-center gap-1">
          <span className="text-xs text-md-sys-color-on-surface-variant">Edited:</span>
          {(
            [
              { label: "Any", value: 0 },
              { label: "24h", value: 24 },
              { label: "7d", value: 168 },
              { label: "30d", value: 720 },
            ] as const
          ).map((opt) => {
            const active = editedWithin === opt.value;
            return (
              <button
                key={opt.label}
                type="button"
                aria-pressed={active}
                className={
                  "rounded-full px-2 py-0.5 text-xs " +
                  (active
                    ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                    : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
                }
                onClick={() => setEditedWithin(opt.value)}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
        <input
          className="mb-3 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {allTags.length > 0 ? (
          <div className="mb-3 flex flex-wrap gap-1">
            <button
              type="button"
              className={
                "rounded-full px-2 py-0.5 text-[10px] " +
                (activeTag === ""
                  ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                  : "border border-md-sys-color-outline-variant")
              }
              onClick={() => setActiveTag("")}
            >
              All
            </button>
            {allTags.map((t) => (
              <button
                key={t}
                type="button"
                className={
                  "rounded-full px-2 py-0.5 text-[10px] " +
                  (activeTag === t
                    ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                    : "border border-md-sys-color-outline-variant")
                }
                onClick={() => setActiveTag(t === activeTag ? "" : t)}
              >
                #{t}
              </button>
            ))}
          </div>
        ) : null}
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
                  {p.pinned ? (
                    <span
                      aria-label="pinned"
                      title="Pinned runbook"
                      className="mr-1 text-md-sys-color-primary"
                    >
                      ⚲
                    </span>
                  ) : null}
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
            <header className="mb-2 flex items-baseline gap-3">
              <div>
                <h2 className="text-2xl font-semibold">{active.title}</h2>
                <p className="text-xs text-md-sys-color-on-surface-variant">
                  {active.slug} · updated {new Date(active.updated_at).toLocaleString()}
                </p>
              </div>
              {canManage ? (
                <button
                  type="button"
                  className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                  onClick={() => {
                    void togglePin(active);
                  }}
                  title="Toggle pin"
                >
                  {active.pinned ? "Unpin" : "Pin"}
                </button>
              ) : null}
              {canManage ? (
                <button
                  type="button"
                  className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                  onClick={() => setEditing((v) => !v)}
                >
                  {editing ? "Cancel" : "Edit"}
                </button>
              ) : null}
              {editing ? (
                <button
                  type="button"
                  className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary"
                  onClick={() => {
                    void saveEdit();
                  }}
                >
                  Save
                </button>
              ) : null}
            </header>
            {editing ? (
              <div className="space-y-2">
                <label className="block">
                  <span className="text-xs text-md-sys-color-on-surface-variant">
                    Tags (comma-separated)
                  </span>
                  <input
                    className="mt-1 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
                    value={draftTags}
                    onChange={(e) => setDraftTags(e.target.value)}
                  />
                </label>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <textarea
                    className="min-h-[24rem] rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 font-mono text-xs"
                    value={draftContent}
                    onChange={(e) => setDraftContent(e.target.value)}
                  />
                  <pre className="min-h-[24rem] whitespace-pre-wrap rounded border border-md-sys-color-outline-variant p-3 text-sm">
                    {draftContent}
                  </pre>
                </div>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap rounded border border-md-sys-color-outline-variant p-3 text-sm">
                {active.content}
              </pre>
            )}
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
