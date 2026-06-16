import { useQuery } from "@tanstack/react-query";

import { Chip } from "@/design-system/components/Chip";
import { api } from "@/lib/api";

interface ReadyResponse {
  status: "ready" | "degraded";
  checks: Record<string, "ok" | "down">;
}

interface VersionResponse {
  version: string;
  commit: string;
  builtAt: string;
}

interface HealthPageProps {
  apiBase?: string;
}

const DEFAULT_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

const LABEL = { db: "Database", redis: "Redis", s3: "Object store" } as const;
const CONNECTED = { db: "Connected", redis: "Reachable", s3: "Bucket OK" } as const;
type CheckKey = keyof typeof LABEL;

export function HealthPage({ apiBase = DEFAULT_BASE }: HealthPageProps) {
  const client = api(apiBase);
  const ready = useQuery<ReadyResponse>({
    queryKey: ["readyz"],
    queryFn: async () => {
      const url = `${apiBase}/readyz`;
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      return (await res.json()) as ReadyResponse;
    },
    refetchInterval: 10_000,
    retry: false,
  });
  const version = useQuery<VersionResponse>({
    queryKey: ["version"],
    queryFn: () => client.get<VersionResponse>("/version"),
    staleTime: Infinity,
  });

  const status = ready.data?.status ?? (ready.isError ? "degraded" : "loading");
  const checks = ready.data?.checks ?? {};

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-lg font-semibold">Adhkar status</h1>
      <ul className="space-y-2 rounded-shape-medium border border-outline-variant bg-surface-container p-4">
        <li className="flex items-center justify-between">
          <span>API</span>
          <span className="flex items-center gap-2">
            <Chip variant={status === "ready" ? "success" : "danger"}>
              {status === "ready" ? "Healthy" : "Degraded"}
            </Chip>
            {version.data && (
              <span className="text-xs text-on-surface-variant">
                v{version.data.version} ({version.data.commit} · {version.data.builtAt})
              </span>
            )}
          </span>
        </li>
        {(["db", "redis", "s3"] as const).map((name: CheckKey) => (
          <li key={name} className="flex items-center justify-between">
            <span>{LABEL[name]}</span>
            <Chip variant={checks[name] === "ok" ? "success" : "danger"}>
              {checks[name] === "ok" ? CONNECTED[name] : "Down"}
            </Chip>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => {
          ready.refetch();
          version.refetch();
        }}
        className="mt-4 rounded-shape-full border border-outline-variant bg-surface-container px-3 py-1.5 text-sm hover:bg-surface-container-high"
      >
        Refresh
      </button>
    </section>
  );
}
