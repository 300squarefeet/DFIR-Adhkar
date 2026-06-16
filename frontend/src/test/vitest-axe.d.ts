// Type augmentation: register vitest-axe's toHaveNoViolations matcher with Vitest's expect.
import "vitest";

declare module "vitest" {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  interface Assertion<T = any> {
    toHaveNoViolations(): void;
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  interface AsymmetricMatchersContaining<T = any> {
    toHaveNoViolations(): void;
  }
}
