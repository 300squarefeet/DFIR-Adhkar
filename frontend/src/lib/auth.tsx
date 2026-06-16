/**
 * AuthContext + useAuth: client-side identity state.
 *
 * Flow:
 *   - On mount, try GET /v1/auth/me with whatever Bearer we have cached.
 *   - On 401, attempt POST /v1/auth/refresh (cookie-backed).
 *   - login()/logout() reset state.
 *
 * Access token lives in memory (not localStorage) to avoid XSS exfil.
 * Refresh token is httpOnly cookie set by the backend.
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

import { api } from "./api";

interface Membership {
  org_id: string;
  org_name: string;
  profile_id: string;
  profile_name: string;
}

interface MeResponse {
  user_id: string;
  email: string;
  display_name: string;
  current_org_id: string | null;
  permissions: string[];
  memberships: Membership[];
}

interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user_id: string;
  current_org_id: string | null;
}

interface AuthState {
  user: MeResponse | null;
  accessToken: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  permissions: Set<string>;
  login(email: string, password: string, mfaCode?: string): Promise<void>;
  logout(): Promise<void>;
  refresh(): Promise<boolean>;
  apiCall<T>(path: string, init?: RequestInit): Promise<T>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const DEFAULT_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

function callJson<T>(
  baseUrl: string,
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (init.accessToken) headers.Authorization = `Bearer ${init.accessToken}`;
  return fetch(baseUrl + path, {
    ...init,
    headers,
    credentials: "include",
  }).then(async (res) => {
    if (!res.ok) {
      let problem: { detail?: string; title?: string } = {};
      try {
        problem = (await res.json()) as typeof problem;
      } catch {
        // non-JSON
      }
      throw new Error(problem.detail ?? problem.title ?? `HTTP ${res.status}`);
    }
    return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
  });
}

interface AuthProviderProps {
  apiBase?: string;
  children: ReactNode;
}

export function AuthProvider({ apiBase = DEFAULT_BASE, children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    loading: true,
  });

  const fetchMe = useCallback(
    async (token: string): Promise<MeResponse | null> => {
      try {
        return await callJson<MeResponse>(apiBase, "/v1/auth/me", {
          accessToken: token,
        });
      } catch {
        return null;
      }
    },
    [apiBase],
  );

  const refresh = useCallback(async (): Promise<boolean> => {
    try {
      const r = await callJson<LoginResponse>(apiBase, "/v1/auth/refresh", {
        method: "POST",
      });
      const me = await fetchMe(r.access_token);
      setState({ user: me, accessToken: r.access_token, loading: false });
      return Boolean(me);
    } catch {
      setState({ user: null, accessToken: null, loading: false });
      return false;
    }
  }, [apiBase, fetchMe]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string, mfaCode?: string) => {
      const r = await callJson<LoginResponse>(apiBase, "/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, mfa_code: mfaCode ?? null }),
      });
      const me = await fetchMe(r.access_token);
      setState({ user: me, accessToken: r.access_token, loading: false });
    },
    [apiBase, fetchMe],
  );

  const logout = useCallback(async () => {
    try {
      if (state.accessToken) {
        await callJson<void>(apiBase, "/v1/auth/logout", {
          method: "POST",
          accessToken: state.accessToken,
        });
      }
    } catch {
      // ignore — we clear local state regardless
    }
    setState({ user: null, accessToken: null, loading: false });
  }, [apiBase, state.accessToken]);

  const apiCall = useCallback(
    <T,>(path: string, init: RequestInit = {}): Promise<T> => {
      const merged: RequestInit & { accessToken?: string } = { ...init };
      if (state.accessToken) merged.accessToken = state.accessToken;
      return callJson<T>(apiBase, path, merged);
    },
    [apiBase, state.accessToken],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      permissions: new Set(state.user?.permissions ?? []),
      login,
      logout,
      refresh,
      apiCall,
    }),
    [state, login, logout, refresh, apiCall],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() must be used within <AuthProvider>");
  return ctx;
}

export { api };
