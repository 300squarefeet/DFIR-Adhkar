import { useNavigate } from "@tanstack/react-router";
import { Command } from "cmdk";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-label="Command palette"
      className="fixed inset-0 z-50 flex items-start justify-center bg-scrim/40 pt-32"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-md rounded-shape-large border border-outline-variant bg-surface-container-high p-2 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <Command label="Command palette">
          <Command.Input
            placeholder="Type a command…"
            className="w-full bg-surface-container-low p-2 text-sm outline-none"
            autoFocus
          />
          <Command.List className="mt-2 max-h-72 overflow-auto">
            <Command.Empty className="p-2 text-sm text-on-surface-variant">
              No results.
            </Command.Empty>
            <Command.Item
              onSelect={() => {
                onOpenChange(false);
                navigate({ to: "/health" });
              }}
              className="cursor-pointer rounded-shape-small p-2 text-sm hover:bg-surface-container aria-selected:bg-surface-container"
            >
              Go to Health
            </Command.Item>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
