/**
 * Org-member autocomplete picker for assignee fields. 250 ms debounce
 * against /v1/users/search. onPick(null, "") clears the assignee.
 */

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";

interface UserHit {
  id: string;
  email: string;
  display_name: string;
}

interface Props {
  onPick: (id: string | null, label: string) => void;
  placeholder?: string;
}

export function UserPicker({ onPick, placeholder = "Search assignee…" }: Props) {
  const { apiCall } = useAuth();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<UserHit[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const params = new URLSearchParams({ limit: "10" });
      if (q.trim()) params.set("q", q.trim());
      apiCall<UserHit[]>(`/v1/users/search?${params.toString()}`)
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
      <div className="flex gap-1">
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
          placeholder={placeholder}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setOpen(true)}
        />
        <button
          type="button"
          className="rounded-full border border-md-sys-color-outline-variant px-2 text-[10px] hover:bg-md-sys-color-surface-container"
          onClick={() => {
            onPick(null, "(unassigned)");
            setQ("");
            setOpen(false);
          }}
          title="Clear assignee"
        >
          Clear
        </button>
      </div>
      {open && hits.length > 0 ? (
        <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-64 overflow-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface text-xs shadow">
          {hits.map((h) => (
            <li key={h.id}>
              <button
                type="button"
                className="block w-full px-2 py-1 text-left hover:bg-md-sys-color-surface-container"
                onClick={() => {
                  onPick(h.id, h.display_name);
                  setQ("");
                  setHits([]);
                  setOpen(false);
                }}
              >
                <span>{h.display_name}</span>{" "}
                <span className="text-md-sys-color-on-surface-variant">{h.email}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
