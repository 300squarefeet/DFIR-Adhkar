import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthPage } from "./HealthPage";

const API = "http://api.test";

function wrap(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

afterEach(() => vi.restoreAllMocks());

describe("<HealthPage>", () => {
  it("shows all checks healthy when /readyz is 200", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.endsWith("/readyz")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ status: "ready", checks: { db: "ok", redis: "ok", s3: "ok" } }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (u.endsWith("/version")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              version: "0.1.0-dev",
              commit: "abc1234",
              builtAt: "2026-06-16T00:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.reject(new Error("unmocked"));
    });
    render(wrap(<HealthPage apiBase={API} />));
    await waitFor(() => expect(screen.getByText(/Healthy/i)).toBeInTheDocument());
    expect(screen.getByText(/abc1234/)).toBeInTheDocument();
  });

  it("shows degraded state when /readyz is 503 with redis down", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.endsWith("/readyz")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              status: "degraded",
              checks: { db: "ok", redis: "down", s3: "ok" },
            }),
            { status: 503, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (u.endsWith("/version")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              version: "0.1.0-dev",
              commit: "abc1234",
              builtAt: "2026-06-16T00:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.reject(new Error("unmocked"));
    });
    render(wrap(<HealthPage apiBase={API} />));
    await waitFor(() => expect(screen.getByText(/Degraded/i)).toBeInTheDocument());
    expect(screen.getByText(/Down/i)).toBeInTheDocument();
  });
});
