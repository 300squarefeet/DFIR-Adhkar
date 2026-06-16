import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { applyTheme, getStoredTheme, setStoredTheme, toggleTheme, type Theme } from "./theme";

describe("theme", () => {
  beforeEach(() => {
    document.documentElement.dataset.theme = "dark";
    window.localStorage.removeItem("adhkar.theme");
  });
  afterEach(() => localStorage.clear());

  it("applyTheme writes data-theme attribute", () => {
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("setStoredTheme persists to localStorage and applies", () => {
    setStoredTheme("light");
    expect(window.localStorage.getItem("adhkar.theme")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("getStoredTheme returns dark default when nothing stored", () => {
    expect(getStoredTheme()).toBe("dark");
  });

  it("getStoredTheme returns the persisted value", () => {
    window.localStorage.setItem("adhkar.theme", "light");
    expect(getStoredTheme()).toBe("light");
  });

  it("toggleTheme flips dark<->light and persists", () => {
    setStoredTheme("dark");
    const next: Theme = toggleTheme();
    expect(next).toBe("light");
    expect(window.localStorage.getItem("adhkar.theme")).toBe("light");
    expect(toggleTheme()).toBe("dark");
  });
});
