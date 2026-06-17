/**
 * Case detail (Phase 3). Shows core fields + nested tasks + comments.
 * Edit-in-place lands later; this is read + comment-add only.
 */

import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { useUserNames } from "@/lib/useUserNames";
import { ObservablePicker } from "@/ui/ObservablePicker";
import { useToast } from "@/ui/Toast";
import { TtpPicker } from "@/ui/TtpPicker";
import { MentionTextarea } from "@/ui/MentionTextarea";
import { UserPicker } from "@/ui/UserPicker";

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
  assignee_id: string | null;
  due_date: string | null;
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

interface AnalyzerInfo {
  name: string;
  supported_types: string[];
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

interface RelatedCaseRow {
  case_id: string;
  number: number;
  title: string;
  severity: number;
  stage: string;
  relation: string;
}

interface EvidenceSummary {
  total: number;
  ioc_total: number;
  by_type: { data_type: string; count: number; ioc_count: number }[];
}

export function CaseDetailPage({ caseId }: Props) {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  // (initial value populated after `c` arrives via useUserNames below)
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
  const [analyzers, setAnalyzers] = useState<AnalyzerInfo[]>([]);
  const [runningAnalyzer, setRunningAnalyzer] = useState<string | null>(null);
  const [ttps, setTtps] = useState<
    { id: string; technique_id: string; tactic: string; procedure_note: string | null }[]
  >([]);
  const [editingTtp, setEditingTtp] = useState<string | null>(null);
  const [ttpDraft, setTtpDraft] = useState("");
  const [editingHeader, setEditingHeader] = useState(false);
  const [headerDraft, setHeaderDraft] = useState({
    title: "",
    severity: 2 as SeverityLevel,
    stage: "open",
  });
  const [headerBusy, setHeaderBusy] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState("");
  const [showAssignee, setShowAssignee] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskMandatory, setNewTaskMandatory] = useState(false);
  const [showNewTask, setShowNewTask] = useState(false);
  const [creatingTask, setCreatingTask] = useState(false);
  const [showAssigneeForTask, setShowAssigneeForTask] = useState<string | null>(null);
  const [editingDueForTask, setEditingDueForTask] = useState<string | null>(null);
  const [dueDraft, setDueDraft] = useState("");
  const [expandedTaskLogs, setExpandedTaskLogs] = useState<string | null>(null);
  const [taskLogs, setTaskLogs] = useState<
    Record<string, { id: string; content: string; created_at: string; author_id: string | null }[]>
  >({});
  const [logDraft, setLogDraft] = useState("");
  const [postingLog, setPostingLog] = useState(false);
  const [relatedCases, setRelatedCases] = useState<RelatedCaseRow[] | null>(null);
  const [evidence, setEvidence] = useState<EvidenceSummary | null>(null);

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
        apiCall<AnalyzerInfo[]>(`/v1/analyzers`)
          .then((a) => {
            if (!cancelled) setAnalyzers(a);
          })
          .catch(() => undefined);
        apiCall<
          { id: string; technique_id: string; tactic: string; procedure_note: string | null }[]
        >(`/v1/cases/${caseId}/ttps`)
          .then((t) => {
            if (!cancelled) setTtps(t);
          })
          .catch(() => undefined);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, caseId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await apiCall<RelatedCaseRow[]>(`/v1/cases/${caseId}/related`);
        if (!cancelled) setRelatedCases(rows);
      } catch {
        if (!cancelled) setRelatedCases([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, caseId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const summary = await apiCall<EvidenceSummary>(
          `/v1/cases/${caseId}/observables/summary`,
        );
        if (!cancelled) setEvidence(summary);
      } catch {
        if (!cancelled) setEvidence(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, caseId]);

  const createTask = async () => {
    if (!newTaskTitle.trim()) return;
    setCreatingTask(true);
    try {
      const created = await apiCall<TaskRow>(`/v1/cases/${caseId}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          title: newTaskTitle.trim(),
          mandatory: newTaskMandatory,
        }),
      });
      setTasks((prev) => [...prev, created]);
      setNewTaskTitle("");
      setNewTaskMandatory(false);
      setShowNewTask(false);
      toast.success(`Task "${created.title}" added.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setCreatingTask(false);
    }
  };

  const setTaskStatus = async (taskId: string, status: string) => {
    try {
      const updated = await apiCall<TaskRow>(`/v1/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const setTaskAssignee = async (
    taskId: string,
    assigneeId: string | null,
    label: string,
  ) => {
    try {
      const updated = await apiCall<TaskRow>(`/v1/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify({ assignee_id: assigneeId }),
      });
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      toast.success(`Task assignee: ${label}`);
      setShowAssigneeForTask(null);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const saveTaskDue = async (taskId: string) => {
    try {
      const updated = await apiCall<TaskRow>(`/v1/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify({
          due_date: dueDraft ? new Date(dueDraft).toISOString() : null,
        }),
      });
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setEditingDueForTask(null);
      toast.success("Due date saved.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const moveTask = async (taskId: string, delta: -1 | 1) => {
    const idx = tasks.findIndex((t) => t.id === taskId);
    const next = idx + delta;
    if (idx < 0 || next < 0 || next >= tasks.length) return;
    const reordered = [...tasks];
    const a = reordered[idx];
    const b = reordered[next];
    if (!a || !b) return;
    reordered[idx] = b;
    reordered[next] = a;
    setTasks(reordered);
    try {
      await apiCall(`/v1/cases/${caseId}/tasks/reorder`, {
        method: "POST",
        body: JSON.stringify({ ordered_ids: reordered.map((t) => t.id) }),
      });
    } catch (e) {
      setTasks(tasks);
      toast.error((e as Error).message);
    }
  };

  const toggleTaskLogs = async (taskId: string) => {
    if (expandedTaskLogs === taskId) {
      setExpandedTaskLogs(null);
      return;
    }
    setExpandedTaskLogs(taskId);
    setLogDraft("");
    if (taskLogs[taskId]) return;
    try {
      const rows = await apiCall<
        { id: string; content: string; created_at: string; author_id: string | null }[]
      >(`/v1/tasks/${taskId}/logs`);
      setTaskLogs((prev) => ({ ...prev, [taskId]: rows }));
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const postTaskLog = async (taskId: string) => {
    if (!logDraft.trim()) return;
    setPostingLog(true);
    try {
      const created = await apiCall<{
        id: string;
        content: string;
        created_at: string;
        author_id: string | null;
      }>(`/v1/tasks/${taskId}/logs`, {
        method: "POST",
        body: JSON.stringify({ content: logDraft.trim() }),
      });
      setTaskLogs((prev) => ({
        ...prev,
        [taskId]: [...(prev[taskId] ?? []), created],
      }));
      setLogDraft("");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setPostingLog(false);
    }
  };

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

  const refreshTtps = async () => {
    try {
      const t = await apiCall<
        { id: string; technique_id: string; tactic: string; procedure_note: string | null }[]
      >(`/v1/cases/${caseId}/ttps`);
      setTtps(t);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const addTtp = async (techniqueId: string, label: string) => {
    try {
      await apiCall(`/v1/cases/${caseId}/ttps`, {
        method: "POST",
        body: JSON.stringify({ technique_id: techniqueId }),
      });
      toast.success(`Added ${label}.`);
      await refreshTtps();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const saveTtpNote = async (ttpId: string) => {
    try {
      const updated = await apiCall<{
        id: string;
        technique_id: string;
        tactic: string;
        procedure_note: string | null;
      }>(`/v1/case-ttps/${ttpId}`, {
        method: "PATCH",
        body: JSON.stringify({ procedure_note: ttpDraft }),
      });
      setTtps((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setEditingTtp(null);
      toast.success("Procedure note saved.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const startHeaderEdit = (c: CaseDetail) => {
    setHeaderDraft({
      title: c.title,
      severity: c.severity,
      stage: c.stage as "open" | "in_progress" | "closed",
    });
    setEditingHeader(true);
  };

  const saveDescription = async () => {
    try {
      const updated = await apiCall<CaseDetail>(`/v1/cases/${caseId}`, {
        method: "PATCH",
        body: JSON.stringify({ description: descDraft }),
      });
      setCase(updated);
      setEditingDesc(false);
      toast.success("Description saved.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const setAssignee = async (assigneeId: string | null, label: string) => {
    try {
      const updated = await apiCall<CaseDetail>(`/v1/cases/${caseId}`, {
        method: "PATCH",
        body: JSON.stringify({ assignee_id: assigneeId }),
      });
      setCase(updated);
      toast.success(`Assignee: ${label}`);
      setShowAssignee(false);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const saveHeader = async () => {
    setHeaderBusy(true);
    try {
      const updated = await apiCall<CaseDetail>(`/v1/cases/${caseId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: headerDraft.title,
          severity: headerDraft.severity,
          stage: headerDraft.stage,
        }),
      });
      setCase(updated);
      setEditingHeader(false);
      toast.success("Case updated.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setHeaderBusy(false);
    }
  };

  const removeTtp = async (ttpId: string) => {
    try {
      await apiCall(`/v1/case-ttps/${ttpId}`, { method: "DELETE" });
      await refreshTtps();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const runAnalyzer = async (observableId: string, analyzerName: string) => {
    setRunningAnalyzer(`${observableId}:${analyzerName}`);
    try {
      await apiCall(
        `/v1/observables/${observableId}/analyzers/${encodeURIComponent(analyzerName)}`,
        { method: "POST", body: "{}" },
      );
      toast.success(`Enqueued ${analyzerName}.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRunningAnalyzer(null);
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

  // Resolve assignee + comment author + task assignee + log author ids →
  // display names through the shared session cache.
  const idsToResolve: (string | null | undefined)[] = [
    c?.assignee_id,
    ...comments.map((cm) => cm.author_id),
    ...tasks.map((t) => t.assignee_id),
    ...Object.values(taskLogs)
      .flat()
      .map((l) => l.author_id),
  ];
  const userNames = useUserNames(idsToResolve);

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
          {editingHeader ? (
            <input
              className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-lg"
              value={headerDraft.title}
              onChange={(e) =>
                setHeaderDraft({ ...headerDraft, title: e.target.value })
              }
            />
          ) : (
            <h1 className="text-2xl font-semibold">{c.title}</h1>
          )}
          {permissions.has("manageCase") ? (
            editingHeader ? (
              <>
                <button
                  type="button"
                  className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary disabled:opacity-50"
                  onClick={() => {
                    void saveHeader();
                  }}
                  disabled={headerBusy}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                  onClick={() => setEditingHeader(false)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                type="button"
                className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                onClick={() => startHeaderEdit(c)}
              >
                Edit
              </button>
            )
          ) : null}
          {!editingHeader ? (
            <button
              type="button"
              className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container disabled:opacity-50"
              onClick={() => {
                void downloadReport();
              }}
              disabled={reportBusy}
            >
              {reportBusy ? "…" : "Download report (.md)"}
            </button>
          ) : null}
          <a
            href={`${(import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"}/v1/cases/${caseId}/report.html`}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
          >
            Print preview
          </a>
          {permissions.has("viewAudit") ? (
            <a
              href={`/admin/audit?entity_type=case&entity_id=${caseId}`}
              className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
              title="Open this case's audit trail"
            >
              Audit trail
            </a>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editingHeader ? (
            <>
              <select
                className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
                value={headerDraft.severity}
                onChange={(e) =>
                  setHeaderDraft({
                    ...headerDraft,
                    severity: Number(e.target.value) as SeverityLevel,
                  })
                }
              >
                <option value={1}>Sev 1 Low</option>
                <option value={2}>Sev 2 Med</option>
                <option value={3}>Sev 3 High</option>
                <option value={4}>Sev 4 Critical</option>
              </select>
              <select
                className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
                value={headerDraft.stage}
                onChange={(e) =>
                  setHeaderDraft({
                    ...headerDraft,
                    stage: e.target.value as "open" | "in_progress" | "closed",
                  })
                }
              >
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="closed">Closed</option>
              </select>
            </>
          ) : (
            <>
              <SeverityBadge level={c.severity} />
              <TLPBadge tlp={c.tlp} />
              <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-xs">
                {c.stage}
              </span>
            </>
          )}
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
        <div className="flex items-center gap-2 text-xs text-md-sys-color-on-surface-variant">
          <span>
            Assignee:{" "}
            {c.assignee_id ? (
              <span className="font-medium text-md-sys-color-on-surface">
                {userNames[c.assignee_id] ?? c.assignee_id.slice(0, 8)}
              </span>
            ) : (
              <span>(unassigned)</span>
            )}
          </span>
          {permissions.has("manageCase") ? (
            <button
              type="button"
              className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container"
              onClick={() => setShowAssignee((v) => !v)}
            >
              {showAssignee ? "Cancel" : "Change"}
            </button>
          ) : null}
        </div>
        {showAssignee && permissions.has("manageCase") ? (
          <UserPicker
            onPick={(id, label) => {
              void setAssignee(id, label);
            }}
            placeholder="Search org members…"
          />
        ) : null}
        {editingDesc && permissions.has("manageCase") ? (
          <div className="space-y-2">
            <textarea
              className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
              rows={4}
              value={descDraft}
              onChange={(e) => setDescDraft(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-xs text-md-sys-color-on-primary"
                onClick={() => {
                  void saveDescription();
                }}
              >
                Save
              </button>
              <button
                type="button"
                className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs"
                onClick={() => setEditingDesc(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <p className="flex-1 whitespace-pre-wrap text-sm">
              {c.description || (
                <span className="text-md-sys-color-on-surface-variant">
                  No description.
                </span>
              )}
            </p>
            {permissions.has("manageCase") ? (
              <button
                type="button"
                className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container"
                onClick={() => {
                  setDescDraft(c.description ?? "");
                  setEditingDesc(true);
                }}
              >
                Edit desc
              </button>
            ) : null}
          </div>
        )}
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
        <div className="mb-2 flex items-center gap-2">
          <h2 className="text-lg font-medium">Tasks ({tasks.length})</h2>
          {permissions.has("manageTask") ? (
            <button
              type="button"
              className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
              onClick={() => setShowNewTask((v) => !v)}
            >
              {showNewTask ? "Cancel" : "+ Task"}
            </button>
          ) : null}
        </div>
        {showNewTask && permissions.has("manageTask") ? (
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <input
              className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="Task title"
              value={newTaskTitle}
              onChange={(e) => setNewTaskTitle(e.target.value)}
            />
            <label className="flex items-center gap-1 text-xs">
              <input
                type="checkbox"
                checked={newTaskMandatory}
                onChange={(e) => setNewTaskMandatory(e.target.checked)}
              />
              required
            </label>
            <button
              type="button"
              className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void createTask();
              }}
              disabled={creatingTask || !newTaskTitle.trim()}
            >
              {creatingTask ? "Adding…" : "Add"}
            </button>
          </div>
        ) : null}
        {tasks.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">No tasks yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {tasks.map((t) => (
              <li
                key={t.id}
                className="rounded border border-md-sys-color-outline-variant px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs">{t.status}</span>
                  <span>{t.title}</span>
                  {t.mandatory ? (
                    <span className="text-xs text-severity-3">required</span>
                  ) : null}
                  {t.assignee_id ? (
                    <span className="text-xs text-md-sys-color-on-surface-variant">
                      @{userNames[t.assignee_id] ?? t.assignee_id.slice(0, 8)}
                    </span>
                  ) : null}
                  {t.due_date ? (
                    <span className="text-xs text-md-sys-color-on-surface-variant">
                      due {new Date(t.due_date).toLocaleDateString()}
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className="ml-auto rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container"
                    onClick={() => {
                      void toggleTaskLogs(t.id);
                    }}
                  >
                    {expandedTaskLogs === t.id ? "Hide log" : "Log"}
                  </button>
                  {permissions.has("manageTask") ? (
                    <>
                      <button
                        type="button"
                        title="Move up"
                        className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container disabled:opacity-30"
                        disabled={tasks.findIndex((x) => x.id === t.id) === 0}
                        onClick={() => {
                          void moveTask(t.id, -1);
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        title="Move down"
                        className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container disabled:opacity-30"
                        disabled={
                          tasks.findIndex((x) => x.id === t.id) ===
                          tasks.length - 1
                        }
                        onClick={() => {
                          void moveTask(t.id, +1);
                        }}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container"
                        onClick={() => {
                          if (editingDueForTask === t.id) {
                            setEditingDueForTask(null);
                          } else {
                            setEditingDueForTask(t.id);
                            setDueDraft(
                              t.due_date ? t.due_date.slice(0, 10) : "",
                            );
                          }
                        }}
                      >
                        {editingDueForTask === t.id ? "Cancel" : "Due"}
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container"
                        onClick={() =>
                          setShowAssigneeForTask(
                            showAssigneeForTask === t.id ? null : t.id,
                          )
                        }
                      >
                        Assignee
                      </button>
                      <select
                        className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-0.5 text-xs"
                        value={t.status}
                        onChange={(e) => {
                          void setTaskStatus(t.id, e.target.value);
                        }}
                      >
                        {["Waiting", "InProgress", "Completed", "Cancelled"].map(
                          (s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ),
                        )}
                      </select>
                    </>
                  ) : null}
                </div>
                {editingDueForTask === t.id && permissions.has("manageTask") ? (
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <input
                      type="date"
                      className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1"
                      value={dueDraft}
                      onChange={(e) => setDueDraft(e.target.value)}
                    />
                    <button
                      type="button"
                      className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-[10px] text-md-sys-color-on-primary"
                      onClick={() => {
                        void saveTaskDue(t.id);
                      }}
                    >
                      Save
                    </button>
                  </div>
                ) : null}
                {showAssigneeForTask === t.id && permissions.has("manageTask") ? (
                  <div className="mt-2">
                    <UserPicker
                      onPick={(id, label) => {
                        void setTaskAssignee(t.id, id, label);
                      }}
                      placeholder="Assign task to…"
                    />
                  </div>
                ) : null}
                {expandedTaskLogs === t.id ? (
                  <div className="mt-2 space-y-1 border-t border-md-sys-color-outline-variant/50 pt-2 text-xs">
                    {(taskLogs[t.id] ?? []).length === 0 ? (
                      <p className="text-md-sys-color-on-surface-variant">
                        No log entries yet.
                      </p>
                    ) : (
                      <ul className="space-y-1">
                        {(taskLogs[t.id] ?? []).map((log) => (
                          <li
                            key={log.id}
                            className="rounded border border-md-sys-color-outline-variant/50 px-2 py-1"
                          >
                            <p className="whitespace-pre-wrap">{log.content}</p>
                            <p className="text-[10px] text-md-sys-color-on-surface-variant">
                              {log.author_id
                                ? (userNames[log.author_id] ??
                                  log.author_id.slice(0, 8))
                                : "system"}{" "}
                              · {new Date(log.created_at).toLocaleString()}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                    {permissions.has("manageTask") ? (
                      <div className="flex flex-col gap-1">
                        <MentionTextarea
                          value={logDraft}
                          onChange={setLogDraft}
                          onSubmit={() => {
                            void postTaskLog(t.id);
                          }}
                          rows={2}
                          placeholder="Add log entry… (@mention; ⌘/Ctrl+Enter)"
                          className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
                        />
                        <div className="flex justify-end">
                          <button
                            type="button"
                            className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-[10px] text-md-sys-color-on-primary disabled:opacity-50"
                            onClick={() => {
                              void postTaskLog(t.id);
                            }}
                            disabled={postingLog || !logDraft.trim()}
                          >
                            {postingLog ? "…" : "Post"}
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
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
                {permissions.has("manageObservable") ? (
                  <select
                    className="ml-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-0.5 text-xs disabled:opacity-50"
                    value=""
                    disabled={runningAnalyzer?.startsWith(o.id + ":") ?? false}
                    onChange={(e) => {
                      const name = e.target.value;
                      if (name) void runAnalyzer(o.id, name);
                    }}
                  >
                    <option value="">
                      {runningAnalyzer?.startsWith(o.id + ":")
                        ? "Enqueuing…"
                        : "Run analyzer…"}
                    </option>
                    {analyzers
                      .filter((a) => a.supported_types.includes(o.data_type))
                      .map((a) => (
                        <option key={a.name} value={a.name}>
                          {a.name}
                        </option>
                      ))}
                  </select>
                ) : null}
                {permissions.has("manageCase") ? (
                  <button
                    type="button"
                    className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
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
        <div className="mb-2 flex items-center gap-2">
          <h2 className="text-lg font-medium">MITRE ATT&amp;CK ({ttps.length})</h2>
        </div>
        {ttps.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            No techniques mapped to this case yet.
          </p>
        ) : (
          <ul className="mb-2 flex flex-wrap gap-1">
            {ttps.map((t) => (
              <li
                key={t.id}
                className="rounded border border-md-sys-color-outline-variant px-2 py-1 text-xs"
              >
                <div className="flex items-center gap-1">
                  <span className="font-mono">{t.technique_id}</span>
                  <span className="text-[10px] text-md-sys-color-on-surface-variant">
                    {t.tactic}
                  </span>
                  {permissions.has("manageCase") ? (
                    <>
                      <button
                        type="button"
                        className="ml-2 rounded-full border border-md-sys-color-outline-variant px-2 text-[10px] hover:bg-md-sys-color-surface-container"
                        onClick={() => {
                          if (editingTtp === t.id) {
                            setEditingTtp(null);
                          } else {
                            setEditingTtp(t.id);
                            setTtpDraft(t.procedure_note ?? "");
                          }
                        }}
                      >
                        {editingTtp === t.id ? "Cancel" : "Note"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          void removeTtp(t.id);
                        }}
                        className="ml-1 text-[10px] text-md-sys-color-on-surface-variant hover:text-severity-4"
                        aria-label="Remove"
                      >
                        ×
                      </button>
                    </>
                  ) : null}
                </div>
                {editingTtp === t.id ? (
                  <div className="mt-1 space-y-1">
                    <textarea
                      className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
                      rows={3}
                      value={ttpDraft}
                      onChange={(e) => setTtpDraft(e.target.value)}
                      placeholder="Procedure note for this technique on this case"
                    />
                    <button
                      type="button"
                      className="rounded-full bg-md-sys-color-primary px-3 py-0.5 text-[10px] text-md-sys-color-on-primary"
                      onClick={() => {
                        void saveTtpNote(t.id);
                      }}
                    >
                      Save
                    </button>
                  </div>
                ) : t.procedure_note ? (
                  <p className="mt-1 text-[10px] text-md-sys-color-on-surface-variant">
                    {t.procedure_note}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {permissions.has("manageCase") ? (
          <TtpPicker
            onPick={(techniqueId: string, label: string) => {
              void addTtp(techniqueId, label);
            }}
          />
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

      {evidence !== null && evidence.total > 0 ? (() => {
        const top = evidence.by_type.slice(0, 5);
        const max = Math.max(...top.map((b) => b.count), 1);
        return (
          <article className="rounded border border-md-sys-color-outline-variant p-3">
            <h2 className="text-sm font-medium">Evidence overview</h2>
            <p className="text-xs text-md-sys-color-on-surface-variant">
              {evidence.total} observables · {evidence.ioc_total} flagged as IOC
            </p>
            <ul className="mt-2 space-y-1 text-xs">
              {top.map((b) => (
                <li key={b.data_type} className="flex items-center gap-2">
                  <span className="w-20 truncate font-mono uppercase">{b.data_type}</span>
                  <div
                    aria-hidden
                    className="h-2 rounded bg-md-sys-color-primary"
                    style={{
                      width: `${(b.count / max) * 100}%`,
                      minWidth: "2px",
                    }}
                  />
                  <span className="ml-auto tabular-nums">{b.count}</span>
                  {b.ioc_count > 0 ? (
                    <span className="text-md-sys-color-on-surface-variant">
                      ({b.ioc_count} IOC)
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </article>
        );
      })() : null}

      <article>
        <h2 className="text-lg font-medium">
          Related cases ({relatedCases?.length ?? "…"})
        </h2>
        {relatedCases === null ? (
          <p className="mt-2 text-sm text-md-sys-color-on-surface-variant">Loading…</p>
        ) : relatedCases.length === 0 ? (
          <p className="mt-2 text-sm text-md-sys-color-on-surface-variant">
            No related cases.
          </p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {relatedCases.map((r) => (
              <li
                key={r.case_id}
                className="flex items-center gap-2 rounded border border-md-sys-color-outline-variant px-3 py-1"
              >
                <Link
                  to="/cases/$caseId"
                  params={{ caseId: r.case_id }}
                  className="hover:underline"
                >
                  <span className="font-mono mr-2">#{r.number}</span>
                  <span>{r.title}</span>
                </Link>
                <span className="ml-auto flex items-center gap-2">
                  <SeverityBadge level={r.severity as SeverityLevel} />
                  <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] uppercase">
                    {r.relation}
                  </span>
                  <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] uppercase">
                    {r.stage}
                  </span>
                </span>
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
                {cm.author_id
                  ? (userNames[cm.author_id] ?? cm.author_id.slice(0, 8))
                  : "system"}{" "}
                · {new Date(cm.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
        {permissions.has("manageCase") ? (
          <div className="flex flex-col gap-2">
            <MentionTextarea
              value={commentDraft}
              onChange={setCommentDraft}
              onSubmit={() => {
                void submitComment();
              }}
              rows={3}
              placeholder="Add a comment… (type @ to mention; ⌘/Ctrl+Enter to send)"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
                onClick={() => {
                  void submitComment();
                }}
                disabled={postBusy || !commentDraft.trim()}
              >
                Comment
              </button>
            </div>
          </div>
        ) : null}
      </article>
    </section>
  );
}
