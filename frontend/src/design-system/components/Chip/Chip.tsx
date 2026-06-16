import type { HTMLAttributes } from "react";

type Variant = "neutral" | "info" | "success" | "warning" | "danger";

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
  /** Optional leading Material Symbol icon (name string). */
  leadingIcon?: string;
}

/** M3 Assist Chip styling per ADR 0005. surface-container + outline border. */
const VARIANT_CLASSES: Record<Variant, string> = {
  neutral: "bg-surface-container text-on-surface border-outline-variant",
  info: "bg-severity-1/20 text-severity-1 border-severity-1/40",
  success: "bg-tlp-green/20 text-tlp-green border-tlp-green/40",
  warning: "bg-severity-2/20 text-severity-2 border-severity-2/40",
  danger: "bg-severity-4/20 text-severity-4 border-severity-4/40",
};

export function Chip({
  variant = "neutral",
  leadingIcon,
  className = "",
  children,
  ...rest
}: ChipProps) {
  return (
    <span
      data-variant={variant}
      className={[
        "inline-flex items-center gap-1 rounded-shape-small border px-2 py-0.5 text-xs font-medium leading-none",
        VARIANT_CLASSES[variant],
        className,
      ].join(" ")}
      {...rest}
    >
      {leadingIcon ? (
        <span aria-hidden className="material-symbols-rounded text-[14px]">
          {leadingIcon}
        </span>
      ) : null}
      {children}
    </span>
  );
}
