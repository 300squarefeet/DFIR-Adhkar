/**
 * Case detail (Phase 3). Shows core fields + nested tasks + comments.
 * Edit-in-place lands later; this is read + comment-add only.
 */

import { useEffect, useState } from "react";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

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
  const [c, setCase] = useState<CaseDetail | null>(null);
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [commentDraft, setCommentDraft] = useState("");
  const [postBusy, setPostBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [responders, setResponders] = useState<Responder[]>([]);
  const [responderBusy, setResponderBusy] = useState<string | null>(null);
  const [lastResponderResult, setLastResponderResult] = useState<ResponderResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cd, ts, cs, rs] = await Promise.all([
          apiCall<CaseDetail>(`/v1/cases/${caseId}`),
          apiCall<TaskRow[]>(`/v1/cases/${caseId}/tasks`),
          apiCall<CommentRow[]>(`/v1/cases/${caseId}/comments`),
          apiCall<Responder[]>(`/v1/responders`).catch(() => [] as Responder[]),
        ]);
        if (cancelled) return;
        setCase(cd);
        setTasks(ts);
        setComments(cs);
        setResponders(rs.filter((r) => r.supported_entity_types.includes("case")));
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, caseId]);

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
