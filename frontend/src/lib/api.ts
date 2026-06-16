export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: ReadonlyArray<unknown>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ProblemDetails,
  ) {
    super(problem.title ?? `HTTP ${status}`);
  }
}

export interface ApiOptions {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface ApiClient {
  get<T>(path: string, opts?: ApiOptions): Promise<T>;
  post<T>(path: string, body?: unknown, opts?: ApiOptions): Promise<T>;
  patch<T>(path: string, body?: unknown, opts?: ApiOptions): Promise<T>;
  del(path: string, opts?: ApiOptions): Promise<void>;
}

export function api(baseUrl: string): ApiClient {
  async function request<T>(
    method: string,
    path: string,
    body: unknown,
    opts: ApiOptions = {},
  ): Promise<T | undefined> {
    const url = baseUrl.replace(/\/$/, "") + path;
    const init: RequestInit = {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(opts.headers ?? {}),
      },
      ...(opts.signal ? { signal: opts.signal } : {}),
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    };
    const res = await fetch(url, init);
    if (!res.ok) {
      let problem: ProblemDetails = {};
      try {
        problem = (await res.json()) as ProblemDetails;
      } catch {
        // non-JSON body
      }
      throw new ApiError(res.status, problem);
    }
    if (res.status === 204) return undefined;
    return (await res.json()) as T;
  }
  return {
    get: <T>(p: string, o?: ApiOptions) => request<T>("GET", p, undefined, o) as Promise<T>,
    post: <T>(p: string, b?: unknown, o?: ApiOptions) =>
      request<T>("POST", p, b, o) as Promise<T>,
    patch: <T>(p: string, b?: unknown, o?: ApiOptions) =>
      request<T>("PATCH", p, b, o) as Promise<T>,
    del: async (p: string, o?: ApiOptions) => {
      await request<undefined>("DELETE", p, undefined, o);
    },
  };
}
