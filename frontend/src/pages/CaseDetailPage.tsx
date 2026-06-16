/**
 * Case detail (Phase 3). Shows core fields + nested tasks + comments.
 * Edit-in-place lands later; this is read + comment-add only.
 */

import { useEffect, useState } from "react";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { ObservablePicker } from "@/ui/ObservablePicker";
import { useToast } from "@/ui/Toast";

interface CaseDetail {
  id: string;
  number: number;
  title: string;
  description: string | null;
  severity: SeverityLevel;
  tlp: TLPValue;
  pap: string;
  stage: string;
  status: string;
  tags: string[];
  assignee_id: string | null;
  created_at: string;
  updated_at: string;
}

interface TaskRow {
  id: string;
  title: string;
  group: string | null;
  status: string;
  order_index: number;
  mandatory: boolean;
}

interface CommentRow {
  id: string;
  author_id: string | null;
  content: string;
  created_at: string;
}

interface CasePageRow {
  id: string;
  slug: string;
  title: string;
  content: string;
  updated_at: string;
}

interface TimelineEntry {
  id: string;
  action: string;
  entity_type: string;
  actor_user_id: string | null;
  created_at: string;
}

interface CaseObservable {
  id: string;
  data_type: string;
  data: string;
  tlp: string;
  tags: string[];
  is_ioc: boolean;
  sighted: boolean;
}

interface CaseReportResponse {
  markdown: string;
  number: number;
}

interface Props {
  caseId: string;
}

interface Responder {
  name: string;
  description: string;
  supported_entity_types: string[];
  confirm_required: boolean;
}

interface ResponderResult {
  status: string;
  summary: string;
}

export function CaseDetailPage({ caseId }: Props) {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [c, setCase] = useState<CaseDetail | null>(null);
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [commentDraft, setCommentDraft] = useState("");
  const [postBusy, setPostBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [responders, setResponders] = useState<Responder[]>([]);
  const [responderBusy, setResponderBusy] = useState<string | null>(null);
  const [lastResponderResult, setLastResponderResult] = useState<ResponderResult | null>(null);
  const [pages, setPages] = useState<CasePageRow[]>([]);
  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [pageDraft, setPageDraft] = useState("");
  const [pageEditing, setPageEditing] = useState(false);
  const [newPageSlug, setNewPageSlug] = useState("");
  const [newPageTitle, setNewPageTitle] = useState("");
  const [showNewPage, setShowNewPage] = useState(false);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [reportBusy, setReportBusy] = useState(false);
  const [caseObs, setCaseObs] = useState<CaseObservable[]>([]);
  const [attachIds, setAttachIds] = useState("");
  const [attachBusy, setAttachBusy] = useState(false);
  const [simCounts, setSimCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cd, ts, cs, rs, ps, tl, obs] = await Promise.all([
          apiCall<CaseDetail>(`/v1/cases/${caseId}`),
          apiCall<TaskRow[]>(`/v1/cases/${caseId}/tasks`),
          apiCall<CommentRow[]>(`/v1/cases/${caseId}/comments`),
          apiCall<Responder[]>(`/v1/responders`).catch(() => [] as Responder[]),
          apiCall<CasePageRow[]>(`/v1/cases/${caseId}/pages`).catch(
            () => [] as CasePageRow[],
          ),
          apiCall<{ entries: TimelineEntry[] }>(
            `/v1/cases/${caseId}/timeline?limit=100`,
          ).catch(() => ({ entries: [] as TimelineEntry[] })),
          apiCall<CaseObservable[]>(`/v1/cases/${caseId}/observables`).catch(
            () => [] as CaseObservable[],
          ),
        ]);
        if (cancelled) return;
        setCase(cd);
        setTasks(ts);
        setComments(cs);
        setResponders(rs.filter((r) => r.supported_entity_types.includes("case")));
        setPages(ps);
        setTimeline(tl.entries);
        setCaseObs(obs);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, caseId]);

  const refreshObservables = async () => {
    try {
      const [obs, sims] = await Promise.all([
        apiCall<CaseObservable[]>(`/v1/cases/${caseId}/observables`),
        apiCall<{ counts: { observable_id: string; total_seen: number }[] }>(
          `/v1/cases/${caseId}/observables/similarity-counts`,
        ).catch(() => ({ counts: [] as { observable_id: string; total_seen: number }[] })),
      ]);
      setCaseObs(obs);
      const m: Record<string, number> = {};
      for (const r of sims.counts) m[r.observable_id] = r.total_seen;
      setSimCounts(m);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const attachObservables = async () => {
    const ids = attachIds
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.length === 0) return;
    setAttachBusy(true);
    try {
      await apiCall<{ attached: number }>(
        `/v1/cases/${caseId}/observables/attach`,
        {
          method: "POST",
          body: JSON.stringify({ observable_ids: ids }),
        },
      );
      setAttachIds("");
      await refreshObservables();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAttachBusy(false);
    }
  };

  const detachObservable = async (observableId: string) => {
    try {
      await apiCall(
        `/v1/cases/${caseId}/observables/${observableId}/detach`,
        { method: "POST", body: "{}" },
      );
      await refreshObservables();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const downloadReport = async () => {
    setReportBusy(true);
    try {
      const r = await apiCall<CaseReportResponse>(`/v1/cases/${caseId}/report`);
      const blob = new Blob([r.markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `adhkar-case-${r.number}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReportBusy(false);
    }
  };

  const activePage = pages.find((p) => p.id === activePageId) ?? null;

  useEffect(() => {
    if (activePage) setPageDraft(activePage.content);
  }, [activePage]);

  const savePage = async () => {
    if (!activePage) return;
    try {
      const updated = await apiCall<CasePageRow>(`/v1/case-pages/${activePage.id}`, {
        method: "PATCH",
        body: JSON.stringify({ content: pageDraft }),
      });
      setPages((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setPageEditing(false);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const createPage = async () => {
    if (!newPageSlug.trim() || !newPageTitle.trim()) return;
    try {
      const created = await apiCall<CasePageRow>(`/v1/cases/${caseId}/pages`, {
        method: "POST",
        body: JSON.stringify({
          slug: newPageSlug.trim(),
          title: newPageTitle.trim(),
          content: "",
        }),
      });
      setPages((prev) => [...prev, created]);
      setActivePageId(created.id);
      setNewPageSlug("");
      setNewPageTitle("");
      setShowNewPage(false);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const runResponder = async (name: string, confirmRequired: boolean) => {
    if (confirmRequired && !window.confirm(`Run responder "${name}" on this case?`)) {
      return;
    }
    const url = window.prompt("Webhook URL to notify");
    if (!url) return;
    setResponderBusy(name);
    setLastResponderResult(null);
    try {
      const r = await apiCall<ResponderResult>(
        `/v1/responders/${encodeURIComponent(name)}/case/${caseId}`,
        {
          method: "POST",
          body: JSON.stringify({ payload: { url, message: `Case ${caseId}` } }),
        },
      );
      setLastResponderResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setResponderBusy(null);
    }
  };

  const submitComment = async () => {
    if (!commentDraft.trim()) return;
    setPostBusy(true);
    try {
      const created = await apiCall<CommentRow>(`/v1/cases/${caseId}/comments`, {
        method: "POST",
        body: JSON.stringify({ content: commentDraft.trim() }),
      });
      setComments((prev) => [...prev, created]);
      setCommentDraft("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPostBusy(false);
    }
  };

  if (error) {
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  }
  if (!c) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-6 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-md-sys-color-on-surface-variant">#{c.number}</span>
          <h1 className="text-2xl font-semibold">{c.title}</h1>
          <button
            type="button"
            className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container disabled:opacity-50"
            onClick={() => {
              void downloadReport();
            }}
            disabled={reportBusy}
          >
            {reportBusy ? "…" : "Download report (.md)"}
          </button>
          <a
            href={`${(import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"}/v1/cases/${caseId}/report.html`}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
          >
            Print preview
          </a>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge level={c.severity} />
          <TLPBadge tlp={c.tlp} />
          <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-xs">
            {c.stage}
          </span>
          <span className="text-xs text-md-sys-color-on-surface-variant">{c.status}</span>
          {c.tags.map((t) => (
            <span
              key={t}
              className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs"
            >
              #{t}
            </span>
          ))}
        </div>
        {c.description ? (
          <p className="whitespace-pre-wrap text-sm">{c.description}</p>
        ) : null}
      </header>

      {responders.length > 0 && permissions.has("manageCase") ? (
        <article>
          <h2 className="mb-2 text-lg font-medium">Responders</h2>
          <div className="flex flex-wrap gap-2">
            {responders.map((r) => (
              <button
                key={r.name}
                type="button"
                title={r.description}
                className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container disabled:opacity-50"
                onClick={() => {
                  void runResponder(r.name, r.confirm_required);
                }}
                disabled={responderBusy === r.name}
              >
                {responderBusy === r.name ? "Running…" : r.name}
              </button>
            ))}
          </div>
          {lastResponderResult ? (
            <p
              className={
                "mt-2 text-xs " +
                (lastResponderResult.status === "ok" ? "text-tlp-green" : "text-severity-4")
              }
            >
              {lastResponderResult.status}: {lastResponderResult.summary}
            </p>
          ) : null}
        </article>
      ) : null}

      <article>
        <h2 className="mb-2 text-lg font-medium">Tasks ({tasks.length})</h2>
        {tasks.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">No tasks yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {tasks.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-3 rounded border border-md-sys-color-outline-variant px-3 py-2"
              >
                <span className="font-mono text-xs">{t.status}</span>
                <span>{t.title}</span>
                {t.mandatory ? (
                  <span className="ml-auto text-xs text-severity-3">required</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </article>

      <article>
        <div className="mb-2 flex items-center gap-2">
          <h2 className="text-lg font-medium">Pages ({pages.length})</h2>
          {permissions.has("manageCase") ? (
            <button
              type="button"
              className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
              onClick={() => setShowNewPage((v) => !v)}
            >
              {showNewPage ? "Cancel" : "+ Page"}
            </button>
          ) : null}
        </div>
        {showNewPage && permissions.has("manageCase") ? (
          <div className="mb-3 flex flex-wrap gap-2">
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
              placeholder="slug"
              value={newPageSlug}
              onChange={(e) => setNewPageSlug(e.target.value)}
            />
            <input
              className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
              placeholder="Title"
              value={newPageTitle}
              onChange={(e) => setNewPageTitle(e.target.value)}
            />
            <button
              type="button"
              className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void createPage();
              }}
              disabled={!newPageSlug.trim() || !newPageTitle.trim()}
            >
              Create
            </button>
          </div>
        ) : null}
        {pages.length > 0 ? (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-[12rem_1fr]">
            <ul className="space-y-1 text-sm">
              {pages.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className={
                      "block w-full truncate rounded px-2 py-1 text-left hover:bg-md-sys-color-surface-container " +
                      (p.id === activePageId ? "bg-md-sys-color-surface-container" : "")
                    }
                    onClick={() => {
                      setActivePageId(p.id);
                      setPageEditing(false);
                    }}
                  >
                    {p.title}
                  </button>
                </li>
              ))}
            </ul>
            <div>
              {activePage ? (
                <article>
                  <div className="mb-1 flex items-center gap-2">
                    <h3 className="text-sm font-medium">{activePage.title}</h3>
                    {permissions.has("manageCase") ? (
                      <button
                        type="button"
                        className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                        onClick={() => setPageEditing((v) => !v)}
                      >
                        {pageEditing ? "Cancel" : "Edit"}
                      </button>
                    ) : null}
                    {pageEditing ? (
                      <button
                        type="button"
                        className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary"
                        onClick={() => {
                          void savePage();
                        }}
                      >
                        Save
                      </button>
                    ) : null}
                  </div>
                  {pageEditing ? (
                    <textarea
                      className="min-h-[16rem] w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 font-mono text-xs"
                      value={pageDraft}
                      onChange={(e) => setPageDraft(e.target.value)}
                    />
                  ) : (
                    <pre className="whitespace-pre-wrap rounded border border-md-sys-color-outline-variant p-3 text-sm">
                      {activePage.content || "(empty)"}
                    </pre>
                  )}
                </article>
              ) : (
                <p className="text-sm text-md-sys-color-on-surface-variant">
                  Select a page.
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-md-sys-color-on-surface-variant">No pages yet.</p>
        )}
      </article>

      <article>
        <h2 className="mb-2 text-lg font-medium">Observables ({caseObs.length})</h2>
        {caseObs.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            No observables attached to this case yet.
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {caseObs.map((o) => (
              <li
                key={o.id}
                className="flex items-center gap-2 rounded border border-md-sys-color-outline-variant px-3 py-1.5"
              >
                <span className="rounded bg-md-sys-color-surface-container px-1.5 py-0.5 font-mono text-[10px] uppercase">
                  {o.data_type}
                </span>
                <span className="break-all font-mono text-xs">{o.data}</span>
                {o.is_ioc ? (
                  <span className="rounded-full bg-severity-4/20 px-2 py-0.5 text-[10px] text-severity-4">
                    IOC
                  </span>
                ) : null}
                {simCounts[o.id] && simCounts[o.id]! > 1 ? (
                  <span className="rounded-full bg-severity-3/20 px-2 py-0.5 text-[10px] text-severity-3">
                    seen {simCounts[o.id]}×
                  </span>
                ) : null}
                {permissions.has("manageCase") ? (
                  <button
                    type="button"
                    className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                    onClick={() => {
                      void detachObservable(o.id);
                    }}
                  >
                    Detach
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {permissions.has("manageCase") ? (
          <div className="mt-2 space-y-2">
            <ObservablePicker
              onPick={(id: string, label: string) => {
                setAttachBusy(true);
                apiCall(`/v1/cases/${caseId}/observables/attach`, {
                  method: "POST",
                  body: JSON.stringify({ observable_ids: [id] }),
                })
                  .then(async () => {
                    toast.success(`Attached ${label}.`);
                    await refreshObservables();
                  })
                  .catch((e: Error) => toast.error(e.message))
                  .finally(() => setAttachBusy(false));
              }}
            />
            <details className="text-xs">
              <summary className="cursor-pointer text-md-sys-color-on-surface-variant">
                Or bulk-attach by UUID
              </summary>
              <div className="mt-2 flex flex-wrap gap-2">
                <input
                  className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
                  placeholder="Observable UUIDs (comma- or space-separated)"
                  value={attachIds}
                  onChange={(e) => setAttachIds(e.target.value)}
                />
                <button
                  type="button"
                  className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
                  onClick={() => {
                    void attachObservables();
                  }}
                  disabled={attachBusy || !attachIds.trim()}
                >
                  {attachBusy ? "…" : "Attach"}
                </button>
              </div>
            </details>
          </div>
        ) : null}
      </article>

      <article>
        <h2 className="mb-2 text-lg font-medium">Timeline ({timeline.length})</h2>
        {timeline.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            No audit entries for this case yet.
          </p>
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

      <article>
        <h2 className="mb-2 text-lg font-medium">Comments ({comments.length})</h2>
        <ul className="mb-3 space-y-2 text-sm">
          {comments.map((cm) => (
            <li
              key={cm.id}
              className="rounded border border-md-sys-color-outline-variant px-3 py-2"
            >
              <p className="whitespace-pre-wrap">{cm.content}</p>
              <p className="mt-1 text-xs text-md-sys-color-on-surface-variant">
                {new Date(cm.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
        {permissions.has("manageCase") ? (
          <div className="flex flex-col gap-2">
            <textarea
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
              rows={3}
              placeholder="Add a comment…"
              value={commentDraft}
              onChange={(e) => setCommentDraft(e.target.value)}
            />
            <button
              type="button"
              className="self-end rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void submitComment();
              }}
              disabled={postBusy || !commentDraft.trim()}
            >
              Comment
            </button>
          </div>
        ) : null}
      </article>
    </section>
  );
}
