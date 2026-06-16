import { Link } from "@tanstack/react-router";

interface Item {
  to?: string;
  label: string;
  icon: string;
  phase?: number;
}

const ITEMS: ReadonlyArray<Item> = [
  { to: "/health", label: "Health", icon: "monitor_heart" },
  { label: "Cases", icon: "work", phase: 3 },
  { label: "Alerts", icon: "warning", phase: 4 },
  { label: "Tasks", icon: "task", phase: 3 },
  { label: "Dashboards", icon: "dashboard", phase: 6 },
  { label: "Knowledge Base", icon: "menu_book", phase: 6 },
  { label: "Admin", icon: "settings", phase: 1 },
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
