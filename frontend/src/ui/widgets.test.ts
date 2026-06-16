import { describe, expect, it } from "vitest";

import { CORE_WIDGETS } from "./widgets";

describe("widget derivations", () => {
  it("open-cases counts non-closed cases", () => {
    const w = CORE_WIDGETS.find((x) => x.id === "open-cases")!;
    const v = w.derive([
      { severity: 3, stage: "open" },
      { severity: 2, stage: "in_progress" },
      { severity: 1, stage: "closed" },
    ]);
    expect(v).toBe(2);
  });

  it("critical-cases counts only sev 4 non-closed", () => {
    const w = CORE_WIDGETS.find((x) => x.id === "critical-cases")!;
    const v = w.derive([
      { severity: 4, stage: "open" },
      { severity: 4, stage: "closed" },
      { severity: 3, stage: "open" },
    ]);
    expect(v).toBe(1);
  });

  it("high-cases counts sev 3+ non-closed", () => {
    const w = CORE_WIDGETS.find((x) => x.id === "high-cases")!;
    const v = w.derive([
      { severity: 3, stage: "open" },
      { severity: 4, stage: "open" },
      { severity: 2, stage: "open" },
      { severity: 4, stage: "closed" },
    ]);
    expect(v).toBe(2);
  });

  it("iocs counts only is_ioc=true rows", () => {
    const w = CORE_WIDGETS.find((x) => x.id === "iocs")!;
    const v = w.derive([
      { is_ioc: true },
      { is_ioc: false },
      { is_ioc: true },
    ]);
    expect(v).toBe(2);
  });

  it("derivations are tolerant of non-array input", () => {
    for (const w of CORE_WIDGETS) {
      expect(w.derive(null)).toBe(0);
      expect(w.derive(undefined)).toBe(0);
      expect(w.derive({})).toBe(0);
    }
  });
});
