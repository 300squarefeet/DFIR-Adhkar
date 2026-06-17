import { Link } from "@tanstack/react-router";
import { useContext, useEffect, useState } from "react";

import { AuthContext } from "@/lib/auth";

interface Item {
  to?: string;
  label: string;
  icon: string;
  phase?: number;
}

const ITEMS: ReadonlyArray<Item> = [
  { to: "/health", label: "Health", icon: "monitor_heart" },
  { to: "/search", label: "Search", icon: "search" },
  { to: "/cases", label: "Cases", icon: "work" },
  { to: "/tasks", label: "Tasks", icon: "task" },
  { to: "/alerts", label: "Alerts", icon: "warning" },
  { to: "/observables", label: "Observables", icon: "fingerprint" },
  { to: "/analyzer-jobs", label: "Analyzers", icon: "biotech" },
  { to: "/adhkar-mind", label: "Adhkar Mind", icon: "psychology" },
  { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { to: "/knowledge-base", label: "Knowledge Base", icon: "menu_book" },
  { to: "/notifications", label: "Notifications", icon: "notifications" },
  { to: "/ttps", label: "MITRE ATT&CK", icon: "shield" },
  { to: "/attack-heatmap", label: "ATT&CK Heatmap", icon: "grid_view" },
  { to: "/mentions", label: "My mentions", icon: "alternate_email" },
  { to: "/admin/users", label: "Admin · Users", icon: "group" },
  { to: "/admin/profiles", label: "Admin · Profiles", icon: "verified_user" },
  { to: "/case-templates", label: "Case Templates", icon: "library_books" },
  { to: "/admin/gdpr", label: "Admin · GDPR", icon: "shield_person" },
  { to: "/admin/audit", label: "Admin · Audit", icon: "history" },
  { to: "/admin/taxonomies", label: "Admin · Taxonomies", icon: "category" },
  { to: "/portal", label: "Portal", icon: "groups" },
];

function useUnreadMentions(): number {
  const ctx = useContext(AuthContext);
  const [n, setN] = useState(0);
  const apiCall = ctx?.apiCall;
  const user = ctx?.user;
  useEffect(() => {
    if (!apiCall || !user) return;
    let cancelled = false;
    const poll = () => {
      apiCall<{ unread: number }>("/v1/mentions/me/unread")
        .then((r) => {
          if (!cancelled) setN(r.unread);
        })
        .catch(() => undefined);
    };
    poll();
    const id = window.setInterval(poll, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [apiCall, user]);
  return n;
}

export function NavigationDrawer() {
  const unread = useUnreadMentions();
  return (
    <nav className="flex h-full w-56 flex-col gap-1 border-r border-outline-variant bg-surface-container-low p-2">
      {ITEMS.map((it) => {
        if (it.to) {
          const badge =
            it.to === "/mentions" && unread > 0 ? unread : null;
          return (
            <Link
              key={it.label}
              to={it.to}
              className="flex h-9 items-center gap-2 rounded-shape-medium px-3 text-sm text-on-surface hover:bg-surface-container-high"
            >
              <span aria-hidden className="material-symbols-rounded text-[18px]">
                {it.icon}
              </span>
              <span>{it.label}</span>
              {badge !== null ? (
                <span className="ml-auto rounded-full bg-md-sys-color-primary px-2 py-0.5 text-[10px] text-md-sys-color-on-primary">
                  {badge > 99 ? "99+" : badge}
                </span>
              ) : null}
            </Link>
          );
        }
        return (
          <button
            key={it.label}
            type="button"
            disabled
            title={`Coming in Phase ${it.phase}`}
            className="flex h-9 items-center gap-2 rounded-shape-medium px-3 text-sm text-on-surface-variant opacity-38"
          >
            <span aria-hidden className="material-symbols-rounded text-[18px]">
              {it.icon}
            </span>
            <span>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
