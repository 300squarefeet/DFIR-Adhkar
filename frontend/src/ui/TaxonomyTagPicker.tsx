/**
 * Tag picker that suggests existing taxonomy entries.
 *
 * Type to filter the union of taxonomy values + currently-applied tags.
 * Enter or click adds; clicking an applied chip removes it.
 */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth";

interface TaxonomyEntry {
  namespace: string;
  predicate: string;
  value: string;
}

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
}

export function TaxonomyTagPicker({ value, onChange }: Props) {
  const { apiCall } = useAuth();
  const [taxonomy, setTaxonomy] = useState<TaxonomyEntry[]>([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    apiCall<TaxonomyEntry[]>("/v1/taxonomies")
      .then(setTaxonomy)
      .catch(() => undefined);
  }, [apiCall]);

  const suggestions = useMemo(() => {
    const q = input.trim().toLowerCase();
    const seed = taxonomy.map(
      (t) => `${t.namespace}:${t.predicate}=${t.value}`,
    );
    const set = new Set(seed);
    if (!q) return Array.from(set).slice(0, 12);
    return Array.from(set)
      .filter((s) => s.toLowerCase().includes(q) && !value.includes(s))
      .slice(0, 12);
  }, [taxonomy, input, value]);

  const add = (tag: string) => {
    const t = tag.trim();
    if (!t) return;
    if (value.includes(t)) return;
    onChange([...value, t]);
    setInput("");
  };

  const remove = (tag: string) => {
    onChange(value.filter((v) => v !== tag));
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {value.length === 0 ? (
          <span className="text-xs text-md-sys-color-on-surface-variant">
            No tags yet.
          </span>
        ) : (
          value.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => remove(t)}
              className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container-high"
              title="Click to remove"
            >
              #{t} ×
            </button>
          ))
        )}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs"
          placeholder="Type tag or pick a taxonomy entry…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(input);
            }
          }}
        />
        <button
          type="button"
          className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
          onClick={() => add(input)}
          disabled={!input.trim()}
        >
          + Tag
        </button>
      </div>
      {suggestions.length > 0 ? (
        <ul className="flex flex-wrap gap-1">
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => add(s)}
                className="rounded-full border border-md-sys-color-outline-variant px-2 py-0.5 text-[10px] hover:bg-md-sys-color-surface-container"
              >
                + {s}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
