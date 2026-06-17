/**
 * Create case form (Phase 3). Minimal: title, severity, tlp, description.
 * On success navigates to the new case's detail page.
 */

import { useEffect, useState } from "react";

import { useRouter } from "@tanstack/react-router";

import type { SeverityLevel } from "@/design-system/components/SeverityBadge";
import type { TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

interface CreatedCase {
  id: string;
  number: number;
}

interface TemplateRow {
  id: string;
  name: string;
  display_name: string;
  severity: number;
  tlp: string;
  pap: string;
  tags: string[];
  tasks: { title?: string; mandatory?: boolean }[];
  summary?: string | null;
}

export function CreateCasePage() {
  const { apiCall, permissions } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<SeverityLevel>(2);
  const [tlp, setTlp] = useState<TLPValue>("amber");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [templateId, setTemplateId] = useState("");

  const canCreate = permissions.has("manageCase");

  useEffect(() => {
    apiCall<TemplateRow[]>("/v1/case-templates")
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, [apiCall]);

  const submit = async () => {
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      let caseId: string;
      if (templateId) {
        const r = await apiCall<{ case_id: string; case_number: number }>(
          `/v1/case-templates/${templateId}/apply`,
          {
            method: "POST",
            body: JSON.stringify({
              title: title.trim(),
              description: description.trim() || null,
            }),
          },
        );
        caseId = r.case_id;
      } else {
        const created = await apiCall<CreatedCase>("/v1/cases", {
          method: "POST",
          body: JSON.stringify({
            title: title.trim(),
            description: description.trim() || null,
            severity,
            tlp,
          }),
        });
        caseId = created.id;
      }
      await router.navigate({ to: "/cases/$caseId", params: { caseId } });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!canCreate) {
    return (
      <section className="p-6">
        <p role="alert">You do not have permission to create cases.</p>
      </section>
    );
  }

  return (
    <section className="max-w-xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">New Case</h1>
      {templates.length > 0 ? (
        <label className="block">
          <span className="text-sm">Template (optional)</span>
          <select
            className="mt-1 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
          >
            <option value="">— scratch —</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.display_name || t.name} · S{t.severity} · TLP {t.tlp} ·{" "}
                {t.tasks.length} task{t.tasks.length === 1 ? "" : "s"}
              </option>
            ))}
          </select>
          {templateId
            ? (() => {
                const t = templates.find((x) => x.id === templateId);
                if (!t) return null;
                return (
                  <div className="mt-2 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface-container p-2 text-xs">
                    {t.summary ? (
                      <p className="mb-1 text-md-sys-color-on-surface-variant">
                        {t.summary}
                      </p>
                    ) : null}
                    <p>
                      <strong>Severity</strong> S{t.severity} ·{" "}
                      <strong>TLP</strong> {t.tlp} · <strong>PAP</strong>{" "}
                      {t.pap}
                    </p>
                    {t.tags.length > 0 ? (
                      <p>
                        <strong>Tags</strong>: {t.tags.join(", ")}
                      </p>
                    ) : null}
                    {t.tasks.length > 0 ? (
                      <details className="mt-1">
                        <summary className="cursor-pointer">
                          {t.tasks.length} task
                          {t.tasks.length === 1 ? "" : "s"} will be created
                        </summary>
                        <ul className="ml-4 mt-1 list-disc">
                          {t.tasks.map((task, i) => (
                            <li key={i}>
                              {task.title ?? "(untitled)"}
                              {task.mandatory ? " · required" : ""}
                            </li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </div>
                );
              })()
            : null}
        </label>
      ) : null}
      <label className="block">
        <span className="text-sm">Title</span>
        <input
          className="mt-1 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={500}
        />
      </label>
      <label className="block">
        <span className="text-sm">Description</span>
        <textarea
          className="mt-1 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>
      <div className="flex gap-4">
        <label className="block">
          <span className="text-sm">Severity</span>
          <select
            className="mt-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
            value={severity}
            onChange={(e) => setSeverity(Number(e.target.value) as SeverityLevel)}
          >
            <option value={1}>1 — Low</option>
            <option value={2}>2 — Medium</option>
            <option value={3}>3 — High</option>
            <option value={4}>4 — Critical</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm">TLP</span>
          <select
            className="mt-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
            value={tlp}
            onChange={(e) => setTlp(e.target.value as TLPValue)}
          >
            <option value="white">White</option>
            <option value="green">Green</option>
            <option value="amber">Amber</option>
            <option value="amber-strict">Amber+Strict</option>
            <option value="red">Red</option>
          </select>
        </label>
      </div>
      {error ? (
        <p role="alert" className="rounded bg-severity-4/20 p-2 text-sm text-severity-4">
          {error}
        </p>
      ) : null}
      <button
        type="button"
        className="rounded-full bg-md-sys-color-primary px-4 py-2 text-sm text-md-sys-color-on-primary disabled:opacity-50"
        onClick={() => {
          void submit();
        }}
        disabled={busy || !title.trim()}
      >
        Create Case
      </button>
    </section>
  );
}
