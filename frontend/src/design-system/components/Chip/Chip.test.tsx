import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import { Chip } from "./Chip";

describe("<Chip>", () => {
  it("renders children", () => {
    render(<Chip>New</Chip>);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("applies variant data-attribute", () => {
    render(<Chip variant="warning">Old</Chip>);
    expect(screen.getByText("Old")).toHaveAttribute("data-variant", "warning");
  });

  it("renders leadingIcon as material symbol", () => {
    render(<Chip leadingIcon="check">Done</Chip>);
    const icon = screen.getByText("check");
    expect(icon).toHaveClass("material-symbols-rounded");
  });

  it("has no a11y violations for all variants", async () => {
    const { container } = render(
      <div>
        <Chip variant="neutral">N</Chip>
        <Chip variant="info">I</Chip>
        <Chip variant="success">S</Chip>
        <Chip variant="warning">W</Chip>
        <Chip variant="danger">D</Chip>
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
