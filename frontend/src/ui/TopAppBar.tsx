import { useState } from "react";

import { Button } from "@/design-system/components/Button";
import { getStoredTheme, toggleTheme } from "@/lib/theme";
import { UserMenu } from "@/ui/UserMenu";

interface TopAppBarProps {
  onOpenPalette: () => void;
}

export function TopAppBar({ onOpenPalette }: TopAppBarProps) {
  const [theme, setTheme] = useState(getStoredTheme());
  const themeIcon = theme === "dark" ? "dark_mode" : "light_mode";
  return (
    <header className="flex h-12 items-center justify-between border-b border-outline-variant bg-surface px-4">
      <div className="flex items-center gap-3">
        <span className="font-brand text-sm font-bold tracking-widest text-primary">ADHKAR</span>
        <span className="text-on-surface-variant">·</span>
        <span className="text-xs text-on-surface-variant">Adhkar IR</span>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="text" size="sm" aria-label="Open command palette" onClick={onOpenPalette}>
          <span aria-hidden className="material-symbols-rounded text-[16px]">
            search
          </span>
          <span>⌘K</span>
        </Button>
        <Button
          variant="text"
          size="sm"
          aria-label="Toggle theme"
          onClick={() => setTheme(toggleTheme())}
        >
          <span aria-hidden className="material-symbols-rounded text-[16px]">
            {themeIcon}
          </span>
        </Button>
        <UserMenu />
      </div>
    </header>
  );
}
