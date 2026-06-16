import { Link } from "@tanstack/react-router";

interface Item {
  to?: string;
  label: string;
  icon: string;
  phase?: number;
}

const ITEMS: ReadonlyArray<Item> = [
  { to: "/health", label: "Health", icon: "monitor_heart" },
  { to: "/cases", label: "Cases", icon: "work" },
  { to: "/alerts", label: "Alerts", icon: "warning" },
  { to: "/observables", label: "Observables", icon: "fingerprint" },
  { to: "/adhkar-mind", label: "Adhkar Mind", icon: "psychology" },
  { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { to: "/knowledge-base", label: "Knowledge Base", icon: "menu_book" },
  { to: "/notifications", label: "Notifications", icon: "notifications" },
  { to: "/ttps", label: "MITRE ATT&CK", icon: "shield" },
  { to: "/admin/users", label: "Admin · Users", icon: "group" },
  { to: "/admin/profiles", label: "Admin · Profiles", icon: "verified_user" },
];

export function NavigationDrawer() {
  return (
    <nav className="flex h-full w-56 flex-col gap-1 border-r border-outline-variant bg-surface-container-low p-2">
      {ITEMS.map((it) => {
        if (it.to) {
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
