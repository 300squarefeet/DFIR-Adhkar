/**
 * Notification settings (Phase 7). List endpoints + rules; create webhook
 * endpoint. Full editor lands later.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface EndpointRow {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
}

interface RuleRow {
  id: string;
  name: string;
  description: string | null;
  endpoint_ids: string[];
  enabled: boolean;
}

export function NotificationsPage() {
  const { apiCall, permissions } = useAuth();
  const [endpoints, setEndpoints] = useState<EndpointRow[]>([]);
  const [rules, setRules] = useState<RuleRow[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [creating, setCreating] = useState(false);

  const canManage = permissions.has("manageConfig");

  const refresh = async () => {
    try {
      const [eps, rs] = await Promise.all([
        apiCall<EndpointRow[]>("/v1/notification-endpoints"),
        apiCall<RuleRow[]>("/v1/notification-rules"),
      ]);
      setEndpoints(eps);
      setRules(rs);
      setLoaded(true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // refresh is intentionally fresh per render here; small page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall]);

  const createWebhook = async () => {
    if (!newName.trim() || !newUrl.trim()) return;
    setCreating(true);
    try {
      await apiCall("/v1/notification-endpoints", {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          kind: "webhook",
          config: { url: newUrl.trim() },
          enabled: true,
        }),
      });
      setNewName("");
      setNewUrl("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCreating(false);
    }
  };

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (!loaded) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Notifications</h1>

      <article>
        <h2 className="mb-2 text-lg font-medium">Endpoints ({endpoints.length})</h2>
        {endpoints.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">No endpoints.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {endpoints.map((e) => (
              <li
                key={e.id}
                className="flex items-center gap-3 rounded border border-md-sys-color-outline-variant px-3 py-2"
              >
                <span className="font-mono text-xs uppercase">{e.kind}</span>
                <span>{e.name}</span>
                {!e.enabled ? (
                  <span className="ml-auto text-xs text-md-sys-color-on-surface-variant">
                    disabled
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {canManage ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="Name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <input
              className="flex-1 rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="https://hooks.example.com/…"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
            />
            <button
              type="button"
              className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void createWebhook();
              }}
              disabled={creating || !newName.trim() || !newUrl.trim()}
            >
              {creating ? "Adding…" : "+ Webhook"}
            </button>
          </div>
        ) : null}
      </article>

      <article>
        <h2 className="mb-2 text-lg font-medium">Rules ({rules.length})</h2>
        {rules.length === 0 ? (
          <p className="text-sm text-md-sys-color-on-surface-variant">No rules.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {rules.map((r) => (
              <li
                key={r.id}
                className="rounded border border-md-sys-color-outline-variant px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium">{r.name}</span>
                  {!r.enabled ? (
                    <span className="text-xs text-md-sys-color-on-surface-variant">
                      disabled
                    </span>
                  ) : null}
                </div>
                {r.description ? (
                  <p className="text-xs text-md-sys-color-on-surface-variant">
                    {r.description}
                  </p>
                ) : null}
                <p className="mt-1 text-xs text-md-sys-color-on-surface-variant">
                  {r.endpoint_ids.length} endpoint
                  {r.endpoint_ids.length === 1 ? "" : "s"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
