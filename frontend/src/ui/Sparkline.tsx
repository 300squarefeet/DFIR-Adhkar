/**
 * Inline SVG sparkline — no charting library.
 *
 * Renders a small polyline from N numeric values; matches surface fg.
 */

export interface SparklineProps {
  values: ReadonlyArray<number>;
  width?: number;
  height?: number;
  className?: string;
  ariaLabel?: string;
}

export function Sparkline({
  values,
  width = 160,
  height = 32,
  className = "",
  ariaLabel = "Trend",
}: SparklineProps) {
  if (values.length === 0) {
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        role="img"
        aria-label={ariaLabel}
        className={className}
      />
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values
    .map((v, i) => {
      const x = stepX * i;
      const y = height - ((v - min) / range) * (height - 2) - 1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const lastX = (values.length - 1) * stepX;
  const lastValue = values[values.length - 1];
  const lastY =
    lastValue === undefined
      ? height
      : height - ((lastValue - min) / range) * (height - 2) - 1;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={ariaLabel}
      className={className}
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lastX.toFixed(1)} cy={lastY.toFixed(1)} r={2} fill="currentColor" />
    </svg>
  );
}
