/**
 * Toast notification system.
 *
 * Provider mounts a transient stack at the top-right; `useToast()` exposes
 * { success, error, info } that any page can call. Toasts auto-dismiss after
 * 5 s; clicking dismisses immediately.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ToastKind = "success" | "error" | "info";

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  success(message: string): void;
  error(message: string): void;
  info(message: string): void;
}

const ToastContext = createContext<ToastApi | null>(null);

let _seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((kind: ToastKind, message: string) => {
    _seq += 1;
    const t: Toast = { id: _seq, kind, message };
    setToasts((prev) => [...prev, t]);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push("success", m),
      error: (m) => push("error", m),
      info: (m) => push("info", m),
    }),
    [push],
  );

  // Auto-dismiss after 5 seconds.
  useEffect(() => {
    if (toasts.length === 0) return;
    const id = window.setTimeout(() => {
      setToasts((prev) => prev.slice(1));
    }, 5000);
    return () => window.clearTimeout(id);
  }, [toasts]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="pointer-events-none fixed right-4 top-4 z-50 flex w-72 flex-col gap-2"
      >
        {toasts.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className={
              "pointer-events-auto rounded border px-3 py-2 text-left text-sm shadow " +
              (t.kind === "success"
                ? "border-tlp-green/40 bg-tlp-green/10 text-tlp-green"
                : t.kind === "error"
                  ? "border-severity-4/40 bg-severity-4/10 text-severity-4"
                  : "border-md-sys-color-outline-variant bg-md-sys-color-surface")
            }
          >
            {t.message}
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/** Optional — returns no-op if no provider mounted (e.g. tests). */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      success: () => undefined,
      error: () => undefined,
      info: () => undefined,
    };
  }
  return ctx;
}
