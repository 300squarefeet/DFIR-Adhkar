/**
 * Case templates list + minimal editor (Phase 6).
 * Create form: name + display_name + severity + tlp + JSON task list.
 */

import { useEffect, useState } from "react";

import { useRouter } from "@tanstack/react-router";

import type { SeverityLevel } from "@/design-system/components/SeverityBadge";
import type { TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

interface TemplateRow {
  id: string;
  name: string;
  display_name: string;
  severity: SeverityLevel;
  tlp: TLPValue;
  tags: string[];
  tasks: Array<{ title: string; mandatory?: boolean }>;
}

export function CaseTemplatesPage() {
  const { apiCall, permissions } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<TemplateRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);

  // Inline create form
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [severity, setSeverity] = useState<SeverityLevel>(2);
  const [tlp, setTlp] = useState<TLPValue>("amber");
  const [tasksJson, setTasksJson] = useState(
    '[\n  { "title": "Triage" },\n  { "title": "Containment", "mandatory": true }\n]',
  );
  const [createBusy, setCreateBusy] = useState(false);

  const canManage = permissions.has("manageConfig");

  const refresh = async () => {
    try {
      const r = await apiCall<TemplateRow[]>("/v1/case-templates");
      setRows(r);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall]);

  const create = async () => {
    if (!name.trim() || !displayName.trim()) return;
    let tasks: unknown;
    try {
      tasks = JSON.parse(tasksJson);
      if (!Array.isArray(tasks)) throw new Error("tasks must be a JSON array");
    } catch (e) {
      setError(`Invalid tasks JSON: ${(e as Error).message}`);
      return;
    }
    setCreateBusy(true);
    try {
      await apiCall("/v1/case-templates", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          display_name: displayName.trim(),
          severity,
          tlp,
          tasks,
        }),
      });
      setName("");
      setDisplayName("");
      setShowCreate(false);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCreateBusy(false);
    }
  };

  const apply = async (t: TemplateRow) => {
    const title = window.prompt(`Title for new case from "${t.display_name}":`);
    if (!title?.trim()) return;
    setApplyingId(t.id);
    try {
      const r = await apiCall<{ case_id: string }>(
        `/v1/case-templates/${t.id}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ title: title.trim() }),
        },
      );
      await router.navigate({ to: "/cases/$caseId", params: { caseId: r.case_id } });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApplyingId(null);
    }
  };

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (rows === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Case Templates</h1>
        {canManage ? (
          <button
            type="button"
            className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary"
            onClick={() => setShowCreate((v) => !v)}
          >
            {showCreate ? "Cancel" : "+ New Template"}
          </button>
        ) : null}
      </div>

      {showCreate && canManage ? (
        <article className="space-y-2 rounded border border-md-sys-color-outline-variant p-3">
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="slug-name (e.g. phishing-investigation)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="Display name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
            <select
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              value={severity}
              onChange={(e) => setSeverity(Number(e.target.value) as SeverityLevel)}
            >
              <option value={1}>Sev 1</option>
              <option value={2}>Sev 2</option>
              <option value={3}>Sev 3</option>
              <option value={4}>Sev 4</option>
            </select>
            <select
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              value={tlp}
              onChange={(e) => setTlp(e.target.value as TLPValue)}
            >
              <option value="white">TLP White</option>
              <option value="green">TLP Green</option>
              <option value="amber">TLP Amber</option>
              <option value="amber-strict">TLP Amber+Strict</option>
              <option value="red">TLP Red</option>
            </select>
          </div>
          <label className="block">
            <span className="text-xs text-md-sys-color-on-surface-variant">
              Tasks (JSON array of {"{ title, mandatory?, order_index? }"})
            </span>
            <textarea
              className="mt-1 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 font-mono text-xs"
              rows={5}
              value={tasksJson}
              onChange={(e) => setTasksJson(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
            onClick={() => {
              void create();
            }}
            disabled={createBusy || !name.trim() || !displayName.trim()}
          >
            {createBusy ? "Creating…" : "Create template"}
          </button>
        </article>
      ) : null}

      {rows.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">No templates yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((t) => (
            <li
              key={t.id}
              className="rounded border border-md-sys-color-outline-variant p-3"
            >
              <div className="flex items-center gap-3">
                <h2 className="font-medium">{t.display_name}</h2>
                <span className="font-mono text-xs text-md-sys-color-on-surface-variant">
                  {t.name}
                </span>
                <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                  {t.tasks.length} task{t.tasks.length === 1 ? "" : "s"} · sev {t.severity}
                </span>
                {permissions.has("manageCase") ? (
                  <button
                    type="button"
                    className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container disabled:opacity-50"
                    onClick={() => {
                      void apply(t);
                    }}
                    disabled={applyingId === t.id}
                  >
                    {applyingId === t.id ? "…" : "Apply"}
                  </button>
                ) : null}
              </div>
              {t.tasks.length > 0 ? (
                <ul className="mt-2 list-inside list-disc text-xs text-md-sys-color-on-surface-variant">
                  {t.tasks.map((ts, i) => (
                    <li key={i}>
                      {ts.title}
                      {ts.mandatory ? " (required)" : ""}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
