import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, expect } from "vitest";
import * as matchers from "vitest-axe/matchers";

expect.extend(matchers);

declare module "vitest" {
  interface Assertion<T = unknown> extends matchers.TestingLibraryMatchers<T, void> {}
}

afterEach(() => cleanup());
