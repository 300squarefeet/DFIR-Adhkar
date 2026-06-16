/**
 * Analyzer jobs viewer (Phase 2).
 * Catalog + per-observable job list + report viewer.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface AnalyzerInfo {
  name: string;
  description: string;
  supported_types: string[];
}

interface AnalyzerJob {
  id: string;
  organization_id: string;
  observable_id: string;
  analyzer_name: string;
  status: string;
  report: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

interface Observable {
  id: string;
  data_type: string;
  data: string;
}

export function AnalyzerJobsPage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [catalog, setCatalog] = useState<AnalyzerInfo[]>([]);
  const [observables, setObservables] = useState<Observable[]>([]);
  const [activeObs, setActiveObs] = useState<string | null>(null);
  const [jobs, setJobs] = useState<AnalyzerJob[]>([]);
  const [activeJob, setActiveJob] = useState<AnalyzerJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cat, obs] = await Promise.all([
          apiCall<AnalyzerInfo[]>("/v1/analyzers"),
          apiCall<Observable[]>("/v1/observables?limit=200"),
        ]);
        if (cancelled) return;
        setCatalog(cat);
        setObservables(obs);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall]);

  const openObservable = async (id: string) => {
    setActiveObs(id);
    setActiveJob(null);
    try {
      const rows = await apiCall<AnalyzerJob[]>(
        `/v1/observables/${id}/analyzer-jobs`,
      );
      setJobs(rows);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  // Auto-poll while any job for the active observable is queued or running.
  useEffect(() => {
    if (!activeObs) return;
    const pending = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (!pending) return;
    const id = window.setInterval(() => {
      apiCall<AnalyzerJob[]>(`/v1/observables/${activeObs}/analyzer-jobs`)
        .then(setJobs)
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(id);
  }, [apiCall, activeObs, jobs]);

  const enqueue = async (analyzerName: string) => {
    if (!activeObs) return;
    try {
      await apiCall<AnalyzerJob>(
        `/v1/observables/${activeObs}/analyzers/${encodeURIComponent(analyzerName)}`,
        { method: "POST", body: "{}" },
      );
      toast.success(`Enqueued ${analyzerName}.`);
      // Re-poll so the new queued row appears immediately.
      const rows = await apiCall<AnalyzerJob[]>(
        `/v1/observables/${activeObs}/analyzer-jobs`,
      );
      setJobs(rows);
    } catch (e) {
      toast.error((e as Error).message);
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

  const activeObservable = observables.find((o) => o.id === activeObs) ?? null;
  const canManage = permissions.has("manageObservable");

  return (
    <section className="grid grid-cols-1 gap-4 p-6 md:grid-cols-[18rem_1fr]">
      <aside>
        <h1 className="mb-2 text-xl font-semibold">Analyzer Jobs</h1>
        <p className="mb-2 text-xs text-md-sys-color-on-surface-variant">
          Pick an observable on the left, then enqueue a registered analyzer.
        </p>
        <ul className="space-y-1 text-sm">
          {observables.map((o) => (
            <li key={o.id}>
              <button
                type="button"
                onClick={() => {
                  void openObservable(o.id);
                }}
                className={
                  "block w-full truncate rounded px-2 py-1 text-left hover:bg-md-sys-color-surface-container " +
                  (o.id === activeObs ? "bg-md-sys-color-surface-container" : "")
                }
              >
                <span className="font-mono text-xs">{o.data_type}</span>{" "}
                <span className="font-mono">{o.data}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <article className="space-y-4">
        {!activeObservable ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            Select an observable to see its analyzer history.
          </p>
        ) : (
          <>
            <header>
              <h2 className="text-lg font-semibold">
                {activeObservable.data_type}: {activeObservable.data}
              </h2>
            </header>

            <article>
              <h3 className="mb-2 text-sm font-medium">Catalog</h3>
              <div className="flex flex-wrap gap-2">
                {catalog
                  .filter((a) => a.supported_types.includes(activeObservable.data_type))
                  .map((a) => (
                    <button
                      key={a.name}
                      type="button"
                      title={a.description}
                      disabled={!canManage}
                      className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container disabled:opacity-50"
                      onClick={() => {
                        void enqueue(a.name);
                      }}
                    >
                      Run {a.name}
                    </button>
                  ))}
              </div>
            </article>

            <article>
              <h3 className="mb-2 text-sm font-medium">Jobs ({jobs.length})</h3>
              {jobs.length === 0 ? (
                <p className="text-sm text-md-sys-color-on-surface-variant">
                  No jobs yet for this observable.
                </p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {jobs.map((j) => (
                    <li key={j.id}>
                      <button
                        type="button"
                        onClick={() => setActiveJob(j)}
                        className={
                          "block w-full rounded border px-3 py-2 text-left text-xs " +
                          (activeJob?.id === j.id
                            ? "border-md-sys-color-primary bg-md-sys-color-surface-container"
                            : "border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
                        }
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono">{j.analyzer_name}</span>
                          <span
                            className={
                              "ml-auto rounded-full px-2 py-0.5 text-[10px] uppercase " +
                              (j.status === "succeeded"
                                ? "bg-tlp-green/20 text-tlp-green"
                                : j.status === "failed"
                                  ? "bg-severity-4/20 text-severity-4"
                                  : "bg-md-sys-color-surface-container")
                            }
                          >
                            {j.status}
                          </span>
                        </div>
                        <div className="font-mono text-[10px] text-md-sys-color-on-surface-variant">
                          {new Date(j.created_at).toLocaleString()}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            {activeJob ? (
              <article className="rounded border border-md-sys-color-outline-variant p-3">
                <h3 className="mb-2 text-sm font-medium">Report</h3>
                {activeJob.error_message ? (
                  <p className="text-xs text-severity-4">{activeJob.error_message}</p>
                ) : null}
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-md-sys-color-surface-container p-2 text-[10px]">
                  {JSON.stringify(activeJob.report ?? {}, null, 2)}
                </pre>
              </article>
            ) : null}
          </>
        )}
      </article>
    </section>
  );
}
