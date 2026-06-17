/**
 * Listens to the live feed for `user.mentioned` events targeting the
 * current user and surfaces a toast with a deep-link to the source case.
 *
 * Rendered once near the top of AppShell so it's mounted on every page.
 */

import { useContext, useEffect, useRef } from "react";

import { AuthContext } from "@/lib/auth";
import { useLiveFeed } from "@/lib/useLiveFeed";
import { useToast } from "@/ui/Toast";

function notifyDesktop(body: string, title: string): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  const N = window.Notification;
  if (N.permission === "granted") {
    try {
      new N(title, { body, tag: "adhkar-mention", silent: false });
    } catch {
      /* ignore: e.g. iOS Safari rejects */
    }
  } else if (N.permission !== "denied") {
    void N.requestPermission().then((p) => {
      if (p === "granted") {
        try {
          new N(title, { body, tag: "adhkar-mention", silent: false });
        } catch {
          /* ignore */
        }
      }
    });
  }
}

export function MentionToastListener() {
  const ctx = useContext(AuthContext);
  const accessToken = ctx?.accessToken ?? null;
  const myId = ctx?.user?.user_id ?? null;
  const toast = useToast();
  const events = useLiveFeed(accessToken);
  const lastSeenIdx = useRef(events.length);

  useEffect(() => {
    if (!myId) return;
    // Only act on events that arrived after we mounted; replay-prevent
    // by tracking the head index of the events ring buffer.
    const head = events.length;
    if (head <= lastSeenIdx.current) return;
    const fresh = events.slice(0, head - lastSeenIdx.current);
    lastSeenIdx.current = head;
    for (const ev of fresh) {
      if (ev.event_type !== "user.mentioned") continue;
      if (ev.entity_id !== myId) continue;
      const diff = ev.diff as
        | { case_id?: string; comment_id?: string; task_log_id?: string }
        | undefined;
      const where = diff?.task_log_id
        ? "a task log"
        : diff?.comment_id
          ? "a comment"
          : "a discussion";
      toast.info(`You were mentioned in ${where}.`);
      // If the tab is in the background, escalate to a desktop notification
      // (best-effort: requires browser permission, which we request lazily).
      if (typeof document !== "undefined" && document.hidden) {
        notifyDesktop(`Mentioned in ${where}`, "Adhkar IR");
      }
    }
  }, [events, myId, toast]);

  return null;
}
