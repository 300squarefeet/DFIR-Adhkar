/**
 * Mentions inbox. Lists @-mentions of the current user (audit_log
 * action='mentioned' for entity=me) with deep links into the source.
 */

import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { useUserNames } from "@/lib/useUserNames";
import { useToast } from "@/ui/Toast";

interface MentionRow {
  id: string;
  actor_user_id: string | null;
  created_at: string;
  diff: Record<string, string | null | undefined>;
}

export function MentionsPage() {
  const { apiCall } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<MentionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const userNames = useUserNames(rows.map((r) => r.actor_user_id ?? ""));

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiCall<MentionRow[]>("/v1/mentions/me")
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiCall, toast]);

  return (
    <section className="p-4">
      <h1 className="mb-2 text-xl font-medium">My mentions ({rows.length})</h1>
      <p className="mb-4 text-xs text-md-sys-color-on-surface-variant">
        Comments and task logs across this organization that include{" "}
        <code>@{"<your display name>"}</code>.
      </p>

      {loading ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">
          No mentions yet.
        </p>
      ) : (
        <ul className="space-y-2 text-sm">
          {rows.map((r) => {
            const caseId = r.diff.case_id ?? null;
            const surface = r.diff.task_log_id
              ? "task log"
              : r.diff.comment_id
                ? "comment"
                : "mention";
            return (
              <li
                key={r.id}
                className="rounded border border-md-sys-color-outline-variant px-3 py-2"
              >
                <p className="text-xs text-md-sys-color-on-surface-variant">
                  {r.actor_user_id
                    ? (userNames[r.actor_user_id] ??
                      r.actor_user_id.slice(0, 8))
                    : "system"}{" "}
                  mentioned you in a {surface} ·{" "}
                  {new Date(r.created_at).toLocaleString()}
                </p>
                {caseId ? (
                  <p className="mt-1">
                    <Link
                      className="text-md-sys-color-primary underline"
                      to="/cases/$caseId"
                      params={{ caseId }}
                    >
                      Open case
                    </Link>
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
