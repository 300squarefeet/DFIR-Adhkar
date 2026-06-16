// Type augmentation: register vitest-axe's toHaveNoViolations matcher with Vitest's expect.
import "vitest";

declare module "vitest" {
  interface Assertion {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
