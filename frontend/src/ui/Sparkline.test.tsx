import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sparkline } from "./Sparkline";

describe("<Sparkline>", () => {
  it("renders an empty svg when given no values", () => {
    const { container } = render(<Sparkline values={[]} ariaLabel="empty" />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.querySelector("polyline")).toBeNull();
  });

  it("renders a polyline with N points for N values", () => {
    const { container } = render(<Sparkline values={[1, 2, 3, 4]} ariaLabel="up" />);
    const poly = container.querySelector("polyline");
    expect(poly).not.toBeNull();
    const points = poly?.getAttribute("points") ?? "";
    expect(points.split(" ").length).toBe(4);
  });

  it("handles a constant series without dividing by zero", () => {
    const { container } = render(<Sparkline values={[5, 5, 5]} ariaLabel="flat" />);
    expect(container.querySelector("polyline")).not.toBeNull();
  });

  it("draws a terminator circle at the last point", () => {
    const { container } = render(<Sparkline values={[1, 5, 3]} ariaLabel="t" />);
    const circle = container.querySelector("circle");
    expect(circle).not.toBeNull();
  });
});
