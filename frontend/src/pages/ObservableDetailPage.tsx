/**
 * Observable detail (Phase 2). Shows the observable + 'seen before' list
 * sourced from /v1/observables/{id}/similar.
 */

import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";

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
  const { apiCall } = useAuth();
  const [obs, setObs] = useState<Observable | null>(null);
  const [matches, setMatches] = useState<SimilarObservable[]>([]);
  const [error, setError] = useState<string | null>(null);

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
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
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

  return (
    <section className="space-y-4 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="rounded bg-md-sys-color-surface-container px-2 py-0.5 font-mono text-xs uppercase">
            {obs.data_type}
          </span>
          <h1 className="break-all font-mono text-lg font-semibold">{obs.data}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TLPBadge tlp={obs.tlp} />
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
          {obs.tags.map((t) => (
            <span
              key={t}
              className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs"
            >
              #{t}
            </span>
          ))}
        </div>
        {obs.message ? (
          <p className="whitespace-pre-wrap text-sm">{obs.message}</p>
        ) : null}
      </header>

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
    </section>
  );
}
