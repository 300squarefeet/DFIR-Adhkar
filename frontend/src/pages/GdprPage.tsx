/**
 * GDPR data-subject admin tool (manageUser only).
 * Lets an admin export a user's data as JSON, or erase their PII.
 */

import { useState } from "react";

import { useAuth } from "@/lib/auth";

interface ExportResponse {
  user: Record<string, unknown>;
  audit_log_entries: Array<Record<string, unknown>>;
  ai_calls: Array<Record<string, unknown>>;
  comments: Array<Record<string, unknown>>;
  task_logs: Array<Record<string, unknown>>;
}

interface EraseResponse {
  user_id: string;
  erased_at: string;
  counts: Record<string, number>;
}

export function GdprPage() {
  const { apiCall, permissions } = useAuth();
  const [userId, setUserId] = useState("");
  const [exportData, setExportData] = useState<ExportResponse | null>(null);
  const [eraseData, setEraseData] = useState<EraseResponse | null>(null);
  const [busy, setBusy] = useState<"export" | "erase" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canManage = permissions.has("manageUser");

  if (!canManage) {
    return (
      <section className="p-6">
        <h1 className="mb-4 text-2xl font-semibold">GDPR</h1>
        <p role="alert">You do not have permission to access GDPR tools.</p>
      </section>
    );
  }

  const doExport = async () => {
    if (!userId.trim()) return;
    setBusy("export");
    setError(null);
    setExportData(null);
    setEraseData(null);
    try {
      const r = await apiCall<ExportResponse>(`/v1/gdpr/users/${userId.trim()}/export`);
      setExportData(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const doErase = async () => {
    if (!userId.trim()) return;
    if (
      !window.confirm(
        `IRREVERSIBLE: redact PII for user ${userId.trim()}? Audit history is preserved.`,
      )
    )
      return;
    setBusy("erase");
    setError(null);
    setEraseData(null);
    try {
      const r = await apiCall<EraseResponse>(
        `/v1/gdpr/users/${userId.trim()}/erase`,
        { method: "POST", body: "{}" },
      );
      setEraseData(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">GDPR Data Subject Tools</h1>
      <p className="text-sm text-md-sys-color-on-surface-variant">
        Export returns everything the platform knows about a user. Erase
        redacts PII but never hard-deletes — audit and case history are
        preserved for forensic continuity.
      </p>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
          placeholder="User UUID"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        />
        <button
          type="button"
          className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
          onClick={() => {
            void doExport();
          }}
          disabled={busy !== null || !userId.trim()}
        >
          {busy === "export" ? "Exporting…" : "Export"}
        </button>
        <button
          type="button"
          className="rounded-full bg-severity-4 px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
          onClick={() => {
            void doErase();
          }}
          disabled={busy !== null || !userId.trim()}
        >
          {busy === "erase" ? "Erasing…" : "Erase PII"}
        </button>
      </div>
      {error ? (
        <p role="alert" className="rounded bg-severity-4/20 p-2 text-sm text-severity-4">
          {error}
        </p>
      ) : null}
      {eraseData ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3 text-sm">
          <p className="font-medium text-severity-3">Erased.</p>
          <p className="text-xs text-md-sys-color-on-surface-variant">
            At {eraseData.erased_at}
          </p>
          <ul className="mt-2 list-inside list-disc text-xs">
            {Object.entries(eraseData.counts).map(([k, v]) => (
              <li key={k}>
                {k}: {v}
              </li>
            ))}
          </ul>
        </article>
      ) : null}
      {exportData ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3">
          <p className="mb-2 text-sm font-medium">Export</p>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-md-sys-color-surface-container p-2 text-[10px]">
            {JSON.stringify(exportData, null, 2)}
          </pre>
        </article>
      ) : null}
    </section>
  );
}
