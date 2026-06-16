/**
 * Activity feed sidebar — last N live events for the active org.
 */

import { useContext } from "react";

import { AuthContext } from "@/lib/auth";
import { useLiveFeed } from "@/lib/useLiveFeed";

function fmtAgo(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  return `${h}h ago`;
}

export function ActivityFeed() {
  // Optional: tests render AppShell without AuthProvider; in that case render nothing.
  const ctx = useContext(AuthContext);
  const accessToken = ctx?.accessToken ?? null;
  const events = useLiveFeed(accessToken);

  if (!accessToken) return null;

  return (
    <aside
      aria-label="Activity feed"
      className="w-64 border-l border-md-sys-color-outline-variant bg-md-sys-color-surface-container-lowest p-3 text-sm"
    >
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-md-sys-color-on-surface-variant">
        Live activity
      </h2>
      {events.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No recent events.</p>
      ) : (
        <ul className="space-y-1">
          {events.map((e, i) => (
            <li
              key={`${e.event_type}-${e.entity_id ?? ""}-${i}`}
              className="rounded border border-md-sys-color-outline-variant/50 px-2 py-1 text-xs"
            >
              <div className="font-mono">{e.event_type}</div>
              {e.entity_id ? (
                <div className="truncate text-md-sys-color-on-surface-variant">
                  {e.entity_id}
                </div>
              ) : null}
              <div className="text-[10px] text-md-sys-color-on-surface-variant">
                {fmtAgo(e.receivedAt)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
