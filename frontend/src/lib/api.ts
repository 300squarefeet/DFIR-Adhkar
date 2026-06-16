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
}

export function api(baseUrl: string): ApiClient {
  async function request<T>(method: string, path: string, opts: ApiOptions = {}): Promise<T> {
    const url = baseUrl.replace(/\/$/, "") + path;
    const res = await fetch(url, {
      method,
      headers: { Accept: "application/json", ...(opts.headers ?? {}) },
      ...(opts.signal ? { signal: opts.signal } : {}),
    });
    if (!res.ok) {
      let problem: ProblemDetails = {};
      try {
        problem = (await res.json()) as ProblemDetails;
      } catch {
        // non-JSON body
      }
      throw new ApiError(res.status, problem);
    }
    return (await res.json()) as T;
  }
  return {
    get: <T>(p: string, o?: ApiOptions) => request<T>("GET", p, o),
  };
}
