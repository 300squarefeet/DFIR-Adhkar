/**
 * Adhkar Portal: external-collaborator view of cases they've been
 * explicitly shared with. Read-only for now; comment-add lands later.
 *
 * Backend: /v1/cases already enforces org-scoping + permissions. For Portal
 * users we list cases where a CaseShare row exists for the current user.
 * The dedicated `/v1/portal/cases` endpoint is RC8 work; for now we use
 * the regular /v1/cases endpoint which returns whatever the user can see.
 */

import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

interface PortalComment {
  id: string;
  content: string;
  created_at: string;
}

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

interface CaseRow {
  id: string;
  number: number;
  title: string;
  severity: SeverityLevel;
  tlp: TLPValue;
  stage: string;
  status: string;
  updated_at: string;
  can_comment: boolean;
  can_upload: boolean;
}

export function PortalPage() {
  const { apiCall, user } = useAuth();
  const [cases, setCases] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [comments, setComments] = useState<PortalComment[]>([]);
  const [commentDraft, setCommentDraft] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiCall<CaseRow[]>("/v1/portal/cases")
      .then((rows) => {
        if (!cancelled) setCases(rows);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  const openCase = async (caseId: string) => {
    setActiveId(caseId);
    setComments([]);
    setCommentDraft("");
    try {
      const rows = await apiCall<PortalComment[]>(
        `/v1/portal/cases/${caseId}/comments`,
      );
      setComments(rows);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const postComment = async () => {
    if (!activeId || !commentDraft.trim()) return;
    setBusy(true);
    try {
      const created = await apiCall<PortalComment>(
        `/v1/portal/cases/${activeId}/comments`,
        {
          method: "POST",
          body: JSON.stringify({ content: commentDraft.trim() }),
        },
      );
      setComments((prev) => [...prev, created]);
      setCommentDraft("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const activeCase = cases?.find((c) => c.id === activeId) ?? null;

  if (error) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">Portal</h1>
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  }
  if (cases === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-4 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Portal</h1>
        <p className="text-sm text-md-sys-color-on-surface-variant">
          Welcome{user ? `, ${user.display_name}` : ""}. These are the cases
          your IR team has shared with you.
        </p>
      </header>
      {cases.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">
          No shared cases yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {cases.map((c) => (
            <li
              key={c.id}
              className={
                "rounded border p-3 " +
                (c.id === activeId
                  ? "border-md-sys-color-primary bg-md-sys-color-surface-container"
                  : "border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
              }
            >
              <div className="flex items-center gap-3 text-sm">
                <button
                  type="button"
                  onClick={() => {
                    void openCase(c.id);
                  }}
                  className="font-mono text-xs hover:underline"
                >
                  #{c.number}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void openCase(c.id);
                  }}
                  className="font-medium hover:underline"
                >
                  {c.title}
                </button>
                <span className="ml-auto flex items-center gap-2">
                  <SeverityBadge level={c.severity} compact />
                  <TLPBadge tlp={c.tlp} />
                  <span className="text-xs text-md-sys-color-on-surface-variant">
                    {c.stage}
                  </span>
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: c.id }}
                    className="text-xs text-md-sys-color-on-surface-variant hover:underline"
                  >
                    full view
                  </Link>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {activeCase ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3">
          <h2 className="mb-2 text-lg font-medium">
            #{activeCase.number} {activeCase.title} — Comments
          </h2>
          {comments.length === 0 ? (
            <p className="text-sm text-md-sys-color-on-surface-variant">
              No comments yet.
            </p>
          ) : (
            <ul className="mb-3 space-y-2 text-sm">
              {comments.map((c) => (
                <li
                  key={c.id}
                  className="rounded border border-md-sys-color-outline-variant px-3 py-2"
                >
                  <p className="whitespace-pre-wrap">{c.content}</p>
                  <p className="mt-1 text-xs text-md-sys-color-on-surface-variant">
                    {new Date(c.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {activeCase.can_comment ? (
            <div className="flex flex-col gap-2">
              <textarea
                className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
                rows={3}
                placeholder="Add a comment for the IR team…"
                value={commentDraft}
                onChange={(e) => setCommentDraft(e.target.value)}
              />
              <button
                type="button"
                className="self-end rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
                onClick={() => {
                  void postComment();
                }}
                disabled={busy || !commentDraft.trim()}
              >
                {busy ? "Posting…" : "Comment"}
              </button>
            </div>
          ) : (
            <p className="text-xs text-md-sys-color-on-surface-variant">
              Read-only share — commenting is not enabled for you on this case.
            </p>
          )}
        </article>
      ) : null}
    </section>
  );
}
