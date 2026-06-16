/**
 * MITRE ATT&CK technique picker. Searches the org's TTP catalog by
 * technique_id or name; debounced 250 ms.
 */

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";

interface CatalogHit {
  id: string;
  technique_id: string;
  name: string;
  tactic: string;
  is_subtechnique: boolean;
}

interface Props {
  onPick: (techniqueId: string, label: string) => void;
}

export function TtpPicker({ onPick }: Props) {
  const { apiCall } = useAuth();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<CatalogHit[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    if (!q.trim()) {
      setHits([]);
      return;
    }
    timer.current = window.setTimeout(() => {
      apiCall<CatalogHit[]>(
        `/v1/ttps/catalog?query=${encodeURIComponent(q.trim())}&limit=10`,
      )
        .then((rows) => {
          setHits(rows);
          setOpen(true);
        })
        .catch(() => undefined);
    }, 250);
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [apiCall, q]);

  return (
    <div className="relative">
      <input
        className="w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
        placeholder="Search MITRE technique (T-id or name)…"
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
                  onPick(h.technique_id, `${h.technique_id} ${h.name}`);
                  setQ("");
                  setHits([]);
                  setOpen(false);
                }}
              >
                <span className="font-mono">{h.technique_id}</span>{" "}
                <span>{h.name}</span>
                <span className="ml-1 text-[10px] text-md-sys-color-on-surface-variant">
                  {h.tactic}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
