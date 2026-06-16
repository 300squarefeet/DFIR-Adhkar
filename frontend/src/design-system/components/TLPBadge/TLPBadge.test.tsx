import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import { TLPBadge, type TLPValue } from "./TLPBadge";

describe("<TLPBadge>", () => {
  const cases: ReadonlyArray<readonly [TLPValue, string]> = [
    ["white", "TLP:WHITE"],
    ["green", "TLP:GREEN"],
    ["amber", "TLP:AMBER"],
    ["amber-strict", "TLP:AMBER+STRICT"],
    ["red", "TLP:RED"],
  ];

  it.each(cases)("tlp=%s renders %s", (tlp, label) => {
    render(<TLPBadge tlp={tlp} />);
    const el = screen.getByRole("status", { name: label });
    expect(el).toHaveTextContent(label);
    expect(el).toHaveAttribute("data-tlp", tlp);
  });

  it("has no a11y violations across values", async () => {
    const { container } = render(
      <div>
        {(["white", "green", "amber", "amber-strict", "red"] as const).map((t) => (
          <TLPBadge key={t} tlp={t} />
        ))}
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
