/**
 * Textarea with inline @-mention typeahead. When the user types `@`
 * followed by at least one word char, a floating menu queries
 * /v1/users/search and on selection replaces the in-progress token
 * with `@<display_name>`.
 */

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";

interface UserHit {
  id: string;
  email: string;
  display_name: string;
}

interface Props {
  value: string;
  onChange: (next: string) => void;
  onSubmit?: () => void;
  rows?: number;
  placeholder?: string;
  className?: string;
}

const TRIGGER_RE = /(?:^|\s)@([A-Za-z0-9_.-]{1,40})$/;

export function MentionTextarea({
  value,
  onChange,
  onSubmit,
  rows = 3,
  placeholder,
  className,
}: Props) {
  const { apiCall } = useAuth();
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const [query, setQuery] = useState<string | null>(null);
  const [hits, setHits] = useState<UserHit[]>([]);
  const [cursor, setCursor] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (query === null) {
      setHits([]);
      return;
    }
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const params = new URLSearchParams({ q: query, limit: "8" });
      apiCall<UserHit[]>(`/v1/users/search?${params.toString()}`)
        .then((rows) => setHits(rows))
        .catch(() => setHits([]));
    }, 200);
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [apiCall, query]);

  function handleChange(next: string, caret: number) {
    onChange(next);
    setCursor(caret);
    const before = next.slice(0, caret);
    const match = TRIGGER_RE.exec(before);
    setQuery(match && match[1] ? match[1] : null);
  }

  function commit(hit: UserHit) {
    const before = value.slice(0, cursor);
    const after = value.slice(cursor);
    const replaced = before.replace(TRIGGER_RE, (full, _q: string) => {
      const prefix = full.startsWith("@") ? "" : full[0];
      return `${prefix}@${hit.display_name} `;
    });
    const next = replaced + after;
    onChange(next);
    setQuery(null);
    setHits([]);
    requestAnimationFrame(() => {
      const ta = taRef.current;
      if (ta) {
        const pos = replaced.length;
        ta.focus();
        ta.setSelectionRange(pos, pos);
      }
    });
  }

  return (
    <div className="relative">
      <textarea
        ref={taRef}
        className={
          className ??
          "w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 text-sm"
        }
        rows={rows}
        placeholder={placeholder}
        value={value}
        onChange={(e) =>
          handleChange(e.target.value, e.target.selectionStart ?? e.target.value.length)
        }
        onKeyDown={(e) => {
          if (onSubmit && (e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            onSubmit();
          }
        }}
        onKeyUp={(e) => {
          const ta = e.currentTarget;
          setCursor(ta.selectionStart ?? ta.value.length);
        }}
        onClick={(e) => {
          const ta = e.currentTarget;
          setCursor(ta.selectionStart ?? ta.value.length);
        }}
      />
      {query !== null && hits.length > 0 ? (
        <ul className="absolute left-0 right-0 z-10 mt-1 max-h-56 overflow-auto rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface text-xs shadow">
          {hits.map((h) => (
            <li key={h.id}>
              <button
                type="button"
                className="block w-full px-2 py-1 text-left hover:bg-md-sys-color-surface-container"
                onMouseDown={(e) => {
                  e.preventDefault();
                  commit(h);
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
