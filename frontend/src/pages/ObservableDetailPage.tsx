/**
 * Observable detail (Phase 2). Shows the observable + 'seen before' list
 * sourced from /v1/observables/{id}/similar.
 */

import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { SeverityBadge, type SeverityLevel } from "@/design-system/components/SeverityBadge";
import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { TaxonomyTagPicker } from "@/ui/TaxonomyTagPicker";
import { useToast } from "@/ui/Toast";

interface Observable {
  id: string;
  data_type: string;
  data: string;
  tlp: TLPValue;
  pap: string;
  tags: string[];
  is_ioc: boolean;
  sighted: boolean;
  ignore_similarity: boolean;
  message: string | null;
  created_at: string;
}

interface CaseRef {
  case_id: string;
  number: number;
  title: string;
  severity: number;
  stage: string;
}

interface SimilarObservable {
  id: string;
  data_type: string;
  data: string;
  is_ioc: boolean;
  sighted: boolean;
  tags: string[];
  case_id: string | null;
  case_number: number | null;
  created_at: string;
}

interface Props {
  observableId: string;
}

export function ObservableDetailPage({ observableId }: Props) {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [obs, setObs] = useState<Observable | null>(null);
  const [matches, setMatches] = useState<SimilarObservable[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editingTags, setEditingTags] = useState(false);
  const [draftTags, setDraftTags] = useState<string[]>([]);
  const [savingTags, setSavingTags] = useState(false);
  const [analyzers, setAnalyzers] = useState<
    { name: string; supported_types: string[] }[]
  >([]);
  const [runBusy, setRunBusy] = useState(false);
  const [caseRefs, setCaseRefs] = useState<CaseRef[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [o, sim] = await Promise.all([
          apiCall<Observable>(`/v1/observables/${observableId}`),
          apiCall<{ matches: SimilarObservable[] }>(
            `/v1/observables/${observableId}/similar`,
          ).catch(() => ({ matches: [] as SimilarObservable[] })),
        ]);
        if (cancelled) return;
        setObs(o);
        setMatches(sim.matches);
        apiCall<{ name: string; supported_types: string[] }[]>("/v1/analyzers")
          .then((a) => {
            if (!cancelled) setAnalyzers(a);
          })
          .catch(() => undefined);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, observableId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const refs = await apiCall<CaseRef[]>(
          `/v1/observables/${observableId}/case-refs`,
        );
        if (!cancelled) setCaseRefs(refs);
      } catch {
        if (!cancelled) setCaseRefs([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiCall, observableId]);

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (!obs) return <section className="p-6">Loading…</section>;

  const startEditTags = () => {
    setDraftTags(obs.tags);
    setEditingTags(true);
  };

  const runAnalyzer = async (analyzerName: string) => {
    setRunBusy(true);
    try {
      await apiCall(
        `/v1/observables/${observableId}/analyzers/${encodeURIComponent(analyzerName)}`,
        { method: "POST", body: "{}" },
      );
      toast.success(`Enqueued ${analyzerName}.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRunBusy(false);
    }
  };

  const toggleFlag = async (field: "is_ioc" | "sighted" | "ignore_similarity") => {
    if (!obs) return;
    try {
      const updated = await apiCall<Observable>(`/v1/observables/${observableId}`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: !obs[field] }),
      });
      setObs(updated);
      toast.success(`Toggled ${field}.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const saveTags = async () => {
    setSavingTags(true);
    try {
      const updated = await apiCall<Observable>(`/v1/observables/${observableId}`, {
        method: "PATCH",
        body: JSON.stringify({ tags: draftTags }),
      });
      setObs(updated);
      toast.success("Tags saved.");
      setEditingTags(false);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSavingTags(false);
    }
  };

  return (
    <section className="space-y-4 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="rounded bg-md-sys-color-surface-container px-2 py-0.5 font-mono text-xs uppercase">
            {obs.data_type}
          </span>
          <h1 className="break-all font-mono text-lg font-semibold">{obs.data}</h1>
          {permissions.has("viewAudit") ? (
            <a
              href={`/admin/audit?entity_type=observable&entity_id=${observableId}`}
              className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
              title="Audit trail for this observable"
            >
              Audit trail
            </a>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TLPBadge tlp={obs.tlp} />
          {permissions.has("manageObservable") ? (
            <>
              <button
                type="button"
                className={
                  "rounded-full px-2 py-0.5 text-xs " +
                  (obs.is_ioc
                    ? "bg-severity-4/20 text-severity-4"
                    : "border border-md-sys-color-outline-variant text-md-sys-color-on-surface-variant")
                }
                onClick={() => {
                  void toggleFlag("is_ioc");
                }}
                title="Click to toggle IOC flag"
              >
                IOC{obs.is_ioc ? " ✓" : ""}
              </button>
              <button
                type="button"
                className={
                  "rounded-full px-2 py-0.5 text-xs " +
                  (obs.sighted
                    ? "bg-severity-3/20 text-severity-3"
                    : "border border-md-sys-color-outline-variant text-md-sys-color-on-surface-variant")
                }
                onClick={() => {
                  void toggleFlag("sighted");
                }}
                title="Click to toggle sighted flag"
              >
                seen{obs.sighted ? " ✓" : ""}
              </button>
              <button
                type="button"
                className={
                  "rounded-full px-2 py-0.5 text-xs " +
                  (obs.ignore_similarity
                    ? "bg-md-sys-color-surface-container"
                    : "border border-md-sys-color-outline-variant text-md-sys-color-on-surface-variant")
                }
                onClick={() => {
                  void toggleFlag("ignore_similarity");
                }}
                title="Click to toggle similarity-ignore"
              >
                ignore-sim{obs.ignore_similarity ? " ✓" : ""}
              </button>
            </>
          ) : (
            <>
              {obs.is_ioc ? (
                <span className="rounded-full bg-severity-4/20 px-2 py-0.5 text-xs text-severity-4">
                  IOC
                </span>
              ) : null}
              {obs.sighted ? (
                <span className="rounded-full bg-severity-3/20 px-2 py-0.5 text-xs text-severity-3">
                  seen
                </span>
              ) : null}
              {obs.ignore_similarity ? (
                <span className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs">
                  similarity ignored
                </span>
              ) : null}
            </>
          )}
          {obs.tags.map((t) => (
            <span
              key={t}
              className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs"
            >
              #{t}
            </span>
          ))}
          {permissions.has("manageObservable") ? (
            <button
              type="button"
              className="ml-auto rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
              onClick={() => (editingTags ? setEditingTags(false) : startEditTags())}
            >
              {editingTags ? "Cancel" : "Edit tags"}
            </button>
          ) : null}
        </div>
        {editingTags && permissions.has("manageObservable") ? (
          <div className="rounded border border-md-sys-color-outline-variant p-3">
            <TaxonomyTagPicker value={draftTags} onChange={setDraftTags} />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                className="rounded-full bg-md-sys-color-primary px-4 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
                onClick={() => {
                  void saveTags();
                }}
                disabled={savingTags}
              >
                {savingTags ? "Saving…" : "Save tags"}
              </button>
            </div>
          </div>
        ) : null}
        {obs.message ? (
          <p className="whitespace-pre-wrap text-sm">{obs.message}</p>
        ) : null}
      </header>

      {permissions.has("manageObservable") &&
      analyzers.filter((a) => a.supported_types.includes(obs.data_type)).length > 0 ? (
        <article>
          <h2 className="mb-2 text-sm font-medium">Run analyzer</h2>
          <select
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs disabled:opacity-50"
            value=""
            disabled={runBusy}
            onChange={(e) => {
              const name = e.target.value;
              if (name) void runAnalyzer(name);
            }}
          >
            <option value="">{runBusy ? "Enqueuing…" : "Pick an analyzer…"}</option>
            {analyzers
              .filter((a) => a.supported_types.includes(obs.data_type))
              .map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}
                </option>
              ))}
          </select>
        </article>
      ) : null}

      <article>
        <h2 className="mb-2 text-lg font-medium">
          Seen before ({matches.length})
        </h2>
        {obs.ignore_similarity ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            Similarity matching is disabled for this observable.
          </p>
        ) : matches.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">
            No previous occurrences of this value in your org.
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {matches.map((m) => (
              <li
                key={m.id}
                className="flex items-center gap-2 rounded border border-md-sys-color-outline-variant px-3 py-1"
              >
                <span className="font-mono text-xs">{m.data_type}</span>
                <span className="font-mono">{m.data}</span>
                {m.is_ioc ? (
                  <span className="rounded-full bg-severity-4/20 px-2 py-0.5 text-[10px] text-severity-4">
                    IOC
                  </span>
                ) : null}
                {m.case_id && m.case_number !== null ? (
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: m.case_id }}
                    className="ml-auto text-xs hover:underline"
                  >
                    case #{m.case_number}
                  </Link>
                ) : (
                  <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                    standalone
                  </span>
                )}
                <span className="text-xs text-md-sys-color-on-surface-variant">
                  {new Date(m.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </article>

      <article>
        <h2 className="text-lg font-medium">
          Cross-case references ({caseRefs === null ? "…" : caseRefs.length})
        </h2>
        {caseRefs === null ? (
          <p className="mt-2 text-sm text-md-sys-color-on-surface-variant">Loading…</p>
        ) : caseRefs.length === 0 ? (
          <p className="mt-2 text-sm text-md-sys-color-on-surface-variant">
            Not seen in any other case.
          </p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {caseRefs.map((r) => (
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
                <SeverityBadge level={r.severity as SeverityLevel} />
                <span className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] uppercase">
                  {r.stage}
                </span>
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
