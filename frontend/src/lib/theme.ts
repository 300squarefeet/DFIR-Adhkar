export type Theme = "dark" | "light";

const STORAGE_KEY = "adhkar.theme";
const DEFAULT_THEME: Theme = "dark";

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function getStoredTheme(): Theme {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : DEFAULT_THEME;
}

export function setStoredTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  applyTheme(theme);
}

export function toggleTheme(): Theme {
  const next: Theme = getStoredTheme() === "dark" ? "light" : "dark";
  setStoredTheme(next);
  return next;
}
