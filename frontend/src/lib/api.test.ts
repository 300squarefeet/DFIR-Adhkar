import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";

const BASE = "http://api.test";

afterEach(() => vi.restoreAllMocks());

describe("api()", () => {
  it("returns JSON for 200 responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const res = await api(BASE).get("/healthz");
    expect(res).toEqual({ status: "ok" });
  });

  it("throws ApiError with structured payload for 4xx/5xx problem+json", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          type: "https://adhkar.dev/problems/internal",
          title: "I",
          status: 500,
          detail: "x",
        }),
        { status: 500, headers: { "Content-Type": "application/problem+json" } },
      ),
    );
    await expect(api(BASE).get("/boom")).rejects.toBeInstanceOf(ApiError);
    try {
      await api(BASE).get("/boom");
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(500);
      expect(err.problem.title).toBe("I");
      expect(err.problem.detail).toBe("x");
    }
  });

  it("propagates X-Request-Id when provided", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await api(BASE).get("/healthz", { headers: { "X-Request-Id": "r-1" } });
    const call = fetchSpy.mock.calls[0]!;
    const init = call[1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-Request-Id"]).toBe("r-1");
  });
});
