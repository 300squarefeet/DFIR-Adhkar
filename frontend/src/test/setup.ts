import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, expect } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";

// Register axe matchers (toHaveNoViolations). Cast to silence types — vitest-axe
// does not declare the matchers' types compatible with Vitest's expect.extend.
expect.extend(axeMatchers as unknown as Parameters<typeof expect.extend>[0]);

afterEach(() => cleanup());
