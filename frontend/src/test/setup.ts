import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, expect } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";

// Register axe matchers (toHaveNoViolations). Cast to silence types — vitest-axe
// does not declare the matchers' types compatible with Vitest's expect.extend.
expect.extend(axeMatchers as unknown as Parameters<typeof expect.extend>[0]);

// happy-dom's localStorage shim does not expose Storage.prototype methods
// (clear/removeItem/setItem/getItem) reliably across versions. Provide a
// deterministic shim so tests can mutate it like a real Storage.
function makeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k: string) => store.get(k) ?? null,
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    removeItem: (k: string) => {
      store.delete(k);
    },
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
  };
}
Object.defineProperty(window, "localStorage", {
  value: makeStorage(),
  writable: true,
  configurable: true,
});

afterEach(() => cleanup());
