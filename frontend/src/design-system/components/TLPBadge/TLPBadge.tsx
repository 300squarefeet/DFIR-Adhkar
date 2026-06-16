import type { HTMLAttributes } from "react";

export type TLPValue = "white" | "green" | "amber" | "amber-strict" | "red";

export interface TLPBadgeProps extends Omit<HTMLAttributes<HTMLSpanElement>, "aria-label"> {
  tlp: TLPValue;
}

const LABELS: Record<TLPValue, string> = {
  white: "TLP:WHITE",
  green: "TLP:GREEN",
  amber: "TLP:AMBER",
  "amber-strict": "TLP:AMBER+STRICT",
  red: "TLP:RED",
};

const COLOR_CLASSES: Record<TLPValue, string> = {
  white: "bg-tlp-white/15 text-tlp-white border-tlp-white/50",
  green: "bg-tlp-green/15 text-tlp-green border-tlp-green/50",
  amber: "bg-tlp-amber/15 text-tlp-amber border-tlp-amber/50",
  "amber-strict": "bg-tlp-amber-strict/15 text-tlp-amber-strict border-tlp-amber-strict/50",
  red: "bg-tlp-red/15 text-tlp-red border-tlp-red/50",
};

export function TLPBadge({ tlp, className = "", ...rest }: TLPBadgeProps) {
  const label = LABELS[tlp];
  return (
    <span
      role="status"
      aria-label={label}
      data-tlp={tlp}
      className={[
        "inline-flex items-center gap-1 rounded-shape-small border px-1.5 py-0.5 text-[0.65rem] font-bold uppercase leading-none tracking-wider",
        COLOR_CLASSES[tlp],
        className,
      ].join(" ")}
      {...rest}
    >
      {label}
    </span>
  );
}
