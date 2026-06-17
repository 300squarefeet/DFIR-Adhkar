import { useEffect, useState, type ReactNode } from "react";

import { applyTheme, getStoredTheme } from "@/lib/theme";
import { ActivityFeed } from "@/ui/ActivityFeed";
import { CommandPalette } from "@/ui/CommandPalette";
import { MentionToastListener } from "@/ui/MentionToastListener";
import { NavigationDrawer } from "@/ui/NavigationDrawer";
import { TopAppBar } from "@/ui/TopAppBar";

export interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    applyTheme(getStoredTheme());
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-screen flex-col bg-surface">
      <TopAppBar onOpenPalette={() => setPaletteOpen(true)} />
      <div className="flex flex-1 overflow-hidden">
        <NavigationDrawer />
        <main className="flex-1 overflow-auto p-4">{children}</main>
        <ActivityFeed />
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <MentionToastListener />
    </div>
  );
}
