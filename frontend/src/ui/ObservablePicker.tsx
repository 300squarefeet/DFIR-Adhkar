/**
 * Autocomplete picker for observables, used by CaseDetailPage to attach
 * existing observables without making the analyst paste raw UUIDs.
 *
 * Debounces queries 250 ms. Calls onPick with the observable id; the
 * parent is responsible for the actual attach POST.
 */

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";

interface ObservableHit {
  id: string;
  data_type: string;
  data: string;
  is_ioc: boolean;
}

interface Props {
  onPick: (id: string, label: string) => void;
  onlyUnattached?: boolean;
}

export function ObservablePicker({ onPick, onlyUnattached = false }: Props) {
  const { apiCall } = useAuth();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<ObservableHit[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    if (!q.trim()) {
      setHits([]);
      return;
    }
    timer.current = window.setTimeout(() => {
      const params = new URLSearchParams({ q: q.trim(), limit: "10" });
      if (onlyUnattached) params.set("only_unattached", "true");
      apiCall<ObservableHit[]>(`/v1/observables/search?${params.toString()}`)
        .then((rows) => {
          setHits(rows);
          setOpen(true);
        })
        .catch(() => undefined);
    }, 250);
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [apiCall, q, onlyUnattached]);

  return (
    <div className="relative flex-1">
      <input
        className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
        placeholder="Search observables to attach…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => {
          if (hits.length > 0) setOpen(true);
        }}
      />
      {open && hits.length > 0 ? (
        <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-64 overflow-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface text-xs shadow">
          {hits.map((h) => (
            <li key={h.id}>
              <button
                type="button"
                className="block w-full px-2 py-1 text-left hover:bg-md-sys-color-surface-container"
                onClick={() => {
                  onPick(h.id, `${h.data_type}: ${h.data}`);
                  setQ("");
                  setHits([]);
                  setOpen(false);
                }}
              >
                <span className="font-mono uppercase text-md-sys-color-on-surface-variant">
                  {h.data_type}
                </span>{" "}
                <span className="font-mono">{h.data}</span>
                {h.is_ioc ? (
                  <span className="ml-1 text-[10px] text-severity-4">IOC</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
