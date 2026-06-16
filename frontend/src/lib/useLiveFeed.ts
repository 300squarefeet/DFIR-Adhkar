/**
 * useLiveFeed — subscribes to /v1/live WebSocket for the active org.
 *
 * Backend emits messages of shape:
 *   { event_type: "case.created", entity_id: "...", diff: { ... }, ... }
 *
 * Reconnects with exponential backoff (capped at 30 s). On unmount the
 * socket is closed and any pending reconnect is canceled.
 */

import { useEffect, useRef, useState } from "react";

export interface LiveEvent {
  event_type: string;
  entity_id?: string | null;
  diff?: Record<string, unknown>;
  receivedAt: number;
}

const DEFAULT_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

function wsUrl(base: string, accessToken: string | null): string {
  const trimmed = base.replace(/\/$/, "");
  const u = new URL(trimmed.replace(/^http/, "ws") + "/v1/live");
  if (accessToken) u.searchParams.set("access_token", accessToken);
  return u.toString();
}

export function useLiveFeed(accessToken: string | null, max = 50): LiveEvent[] {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const reconnectRef = useRef<number | null>(null);
  const closedRef = useRef(false);

  useEffect(() => {
    if (!accessToken) return;
    closedRef.current = false;
    let attempt = 0;
    let ws: WebSocket | null = null;

    const connect = () => {
      ws = new WebSocket(wsUrl(DEFAULT_BASE, accessToken));
      ws.addEventListener("open", () => {
        attempt = 0;
      });
      ws.addEventListener("message", (e) => {
        try {
          const parsed = JSON.parse(String(e.data)) as Omit<LiveEvent, "receivedAt">;
          const event: LiveEvent = { ...parsed, receivedAt: Date.now() };
          setEvents((prev) => [event, ...prev].slice(0, max));
        } catch {
          // ignore malformed frames
        }
      });
      const scheduleReconnect = () => {
        if (closedRef.current) return;
        attempt += 1;
        const delay = Math.min(30_000, 500 * 2 ** Math.min(attempt, 6));
        reconnectRef.current = window.setTimeout(connect, delay);
      };
      ws.addEventListener("close", scheduleReconnect);
      ws.addEventListener("error", () => {
        ws?.close();
      });
    };

    connect();
    return () => {
      closedRef.current = true;
      if (reconnectRef.current !== null) {
        window.clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
      ws?.close();
    };
  }, [accessToken, max]);

  return events;
}
