/**
 * useUserNames — cached lookups of {user_id → display_name}.
 *
 * Resolves a set of user UUIDs to their display names through
 * /v1/users/{id}, deduping requests and caching per-session. Pages
 * that show assignee chips, comment authors, etc. just pass the set
 * of ids and read `names[id]` to render.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface UserInfo {
  id: string;
  email: string;
  display_name: string;
}

const _cache = new Map<string, string>();
const _inflight = new Map<string, Promise<string>>();

async function fetchOne(
  apiCall: <T>(p: string) => Promise<T>,
  id: string,
): Promise<string> {
  const cached = _cache.get(id);
  if (cached !== undefined) return cached;
  const inflight = _inflight.get(id);
  if (inflight) return inflight;
  const p = apiCall<UserInfo>(`/v1/users/${id}`)
    .then((u) => {
      const name = u.display_name || u.email || id.slice(0, 8);
      _cache.set(id, name);
      _inflight.delete(id);
      return name;
    })
    .catch(() => {
      const fallback = id.slice(0, 8);
      _cache.set(id, fallback);
      _inflight.delete(id);
      return fallback;
    });
  _inflight.set(id, p);
  return p;
}

export function useUserNames(ids: ReadonlyArray<string | null | undefined>): Record<string, string> {
  const { apiCall } = useAuth();
  const [names, setNames] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const id of ids) {
      if (id && _cache.has(id)) init[id] = _cache.get(id)!;
    }
    return init;
  });

  useEffect(() => {
    let cancelled = false;
    const unique = Array.from(new Set(ids.filter((x): x is string => Boolean(x))));
    const missing = unique.filter((id) => !_cache.has(id));
    if (missing.length === 0) return;
    Promise.all(missing.map((id) => fetchOne(apiCall, id)))
      .then((vals) => {
        if (cancelled) return;
        setNames((prev) => {
          const next = { ...prev };
          missing.forEach((id, i) => {
            next[id] = vals[i] ?? id.slice(0, 8);
          });
          return next;
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [apiCall, ids]);

  return names;
}
