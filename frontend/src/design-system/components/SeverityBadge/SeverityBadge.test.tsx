import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import { SeverityBadge } from "./SeverityBadge";

describe("<SeverityBadge>", () => {
  it.each([
    [1, "Low"],
    [2, "Medium"],
    [3, "High"],
    [4, "Critical"],
  ] as const)("level %i renders label %s with text and aria-label", (level, label) => {
    render(<SeverityBadge level={level} />);
    const el = screen.getByRole("status", { name: new RegExp(label, "i") });
    expect(el).toHaveTextContent(label);
    expect(el).toHaveAttribute("aria-label", expect.stringContaining(label));
    expect(el).toHaveAttribute("data-severity", String(level));
  });

  it("compact variant hides text but keeps aria-label", () => {
    render(<SeverityBadge level={3} compact />);
    const el = screen.getByRole("status");
    expect(el).toHaveTextContent("");
    expect(el).toHaveAttribute("aria-label", expect.stringContaining("High"));
  });

  it("has no a11y violations across levels", async () => {
    const { container } = render(
      <div>
        {[1, 2, 3, 4].map((l) => (
          <SeverityBadge key={l} level={l as 1 | 2 | 3 | 4} />
        ))}
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
