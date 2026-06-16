import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "filled" | "tonal" | "outlined" | "text" | "error";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Optional leading Material Symbol icon (string name of the symbol). */
  icon?: ReactNode;
}

/** M3 Common Button color schemes; on-* colors guarantee AA contrast. */
const VARIANT_CLASSES: Record<Variant, string> = {
  filled:
    "bg-primary text-on-primary hover:brightness-110 focus-visible:ring-2 focus-visible:ring-primary",
  tonal:
    "bg-secondary-container text-on-secondary-container hover:brightness-110 focus-visible:ring-2 focus-visible:ring-secondary",
  outlined:
    "bg-transparent text-primary border border-outline hover:bg-surface-container-high focus-visible:ring-2 focus-visible:ring-primary",
  text: "bg-transparent text-primary hover:bg-surface-container-high focus-visible:ring-2 focus-visible:ring-primary",
  error:
    "bg-error text-on-error hover:brightness-110 focus-visible:ring-2 focus-visible:ring-error",
};

/** Density override per ADR 0005: tighter than stock M3. */
const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-7 px-3 text-[var(--md-sys-typescale-label-medium-size)]",
  md: "h-9 px-4 text-[var(--md-sys-typescale-label-large-size)]",
  lg: "h-11 px-6 text-[var(--md-sys-typescale-title-medium-size)]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "filled",
    size = "md",
    loading = false,
    disabled,
    icon,
    className = "",
    children,
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;
  const classes = [
    "inline-flex items-center justify-center gap-2 rounded-shape-full font-medium transition-[background-color,color,filter] outline-none",
    "disabled:opacity-38 disabled:cursor-not-allowed",
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    className,
  ].join(" ");
  return (
    <button
      ref={ref}
      className={classes}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      style={{
        transitionDuration: "var(--md-sys-motion-duration-short2)",
        transitionTimingFunction: "var(--md-sys-motion-easing-standard)",
      }}
      {...rest}
    >
      {loading ? (
        <span aria-hidden className="material-symbols-rounded animate-spin text-[18px]">
          progress_activity
        </span>
      ) : icon ? (
        <span aria-hidden className="material-symbols-rounded text-[18px]">
          {icon}
        </span>
      ) : null}
      {children}
    </button>
  );
});
