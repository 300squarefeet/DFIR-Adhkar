import type { HTMLAttributes } from "react";

export type SeverityLevel = 1 | 2 | 3 | 4;

export interface SeverityBadgeProps extends Omit<HTMLAttributes<HTMLSpanElement>, "aria-label"> {
  level: SeverityLevel;
  compact?: boolean;
}

const LABELS: Record<SeverityLevel, string> = {
  1: "Low",
  2: "Medium",
  3: "High",
  4: "Critical",
};

const COLOR_CLASSES: Record<SeverityLevel, string> = {
  1: "bg-severity-1/20 text-severity-1 border-severity-1/40",
  2: "bg-severity-2/20 text-severity-2 border-severity-2/40",
  3: "bg-severity-3/20 text-severity-3 border-severity-3/40",
  4: "bg-severity-4/20 text-severity-4 border-severity-4/40",
};

export function SeverityBadge({
  level,
  compact = false,
  className = "",
  ...rest
}: SeverityBadgeProps) {
  const label = LABELS[level];
  const ariaLabel = `Severity: ${label}`;
  const base = "inline-flex items-center gap-1 rounded-shape-small border font-medium leading-none";
  const sizing = compact ? "h-3 w-3 p-0" : "px-1.5 py-0.5 text-xs";
  return (
    <span
      role="status"
      aria-label={ariaLabel}
      data-severity={level}
      className={[base, sizing, COLOR_CLASSES[level], className].join(" ")}
      {...rest}
    >
      {!compact && label}
    </span>
  );
}
