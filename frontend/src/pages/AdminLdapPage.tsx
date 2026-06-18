/**
 * Admin: LDAP / Active Directory providers management (Phase 11 / v1.1.0).
 *
 * Lists providers, surfaces Edit drawer with full LdapProviderIn fields
 * (bind_password is write-only — presence means rotate), per-provider
 * mappings table with inline Add / Delete, and a Test-connection button
 * that shows ok/error inline per row.
 */

import { Fragment, useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

// ---------------------------------------------------------------------------
// Interfaces (mirror the backend schemas)
// ---------------------------------------------------------------------------

interface LdapProvider {
  id: string;
  name: string;
  server_uris: string[];
  bind_dn: string;
  base_dn: string;
  enabled: boolean;
  priority: number;
  tls_required: boolean;
  allow_insecure: boolean;
}

interface LdapGroupMapping {
  id: string;
  ldap_provider_id: string;
  group_dn: string;
  organization_id: string;
  profile_id: string;
}

interface TestConnectionResult {
  ok: boolean;
  server_uri_used: string | null;
  error: string | null;
  duration_ms: number;
}

interface OrgRow {
  id: string;
  name: string;
}

interface ProfileRow {
  id: string;
  name: string;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function AdminLdapPage() {
  const { apiCall } = useAuth();

  const [providers, setProviders] = useState<LdapProvider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<LdapProvider | "new" | null>(null);
  const [mappings, setMappings] = useState<Record<string, LdapGroupMapping[]>>({});
  const [testResult, setTestResult] = useState<Record<string, TestConnectionResult>>({});
  const [testBusy, setTestBusy] = useState<Record<string, boolean>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const list = await apiCall<LdapProvider[]>("/v1/admin/ldap-providers");
      setProviders(list);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall]);

  const refreshMappings = async (providerId: string) => {
    try {
      const data = await apiCall<LdapGroupMapping[]>(
        `/v1/admin/ldap-providers/${providerId}/mappings`,
      );
      setMappings((m) => ({ ...m, [providerId]: data }));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const runTest = async (provider: LdapProvider) => {
    setTestBusy((b) => ({ ...b, [provider.id]: true }));
    try {
      const r = await apiCall<TestConnectionResult>(
        `/v1/admin/ldap-providers/${provider.id}/test-connection`,
        { method: "POST" },
      );
      setTestResult((t) => ({ ...t, [provider.id]: r }));
    } catch (e) {
      setTestResult((t) => ({
        ...t,
        [provider.id]: {
          ok: false,
          server_uri_used: null,
          error: (e as Error).message,
          duration_ms: 0,
        },
      }));
    } finally {
      setTestBusy((b) => ({ ...b, [provider.id]: false }));
    }
  };

  const softDelete = async (provider: LdapProvider) => {
    if (
      !window.confirm(
        `Delete provider "${provider.name}"? This will disable LDAP authentication for this directory.`,
      )
    )
      return;
    try {
      await apiCall(`/v1/admin/ldap-providers/${provider.id}`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const toggleExpand = (id: string) => {
    const next = expandedId === id ? null : id;
    setExpandedId(next);
    if (next) void refreshMappings(next);
  };

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
        <button
          type="button"
          className="mt-2 text-sm text-md-sys-color-primary underline"
          onClick={() => setError(null)}
        >
          Dismiss
        </button>
      </section>
    );

  return (
    <section className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">LDAP / Active Directory Providers</h1>
        <button
          type="button"
          className="rounded-full bg-md-sys-color-primary px-4 py-1.5 text-sm font-medium text-md-sys-color-on-primary hover:brightness-110"
          onClick={() => setEditing("new")}
        >
          Add provider
        </button>
      </div>

      {providers.length === 0 ? (
        <p className="text-sm text-md-sys-color-on-surface-variant">
          No LDAP providers configured.
        </p>
      ) : (
        <table className="w-full table-auto border-collapse text-sm">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant text-left">
              <th className="py-2 pr-3">Name</th>
              <th className="py-2 pr-3">Servers</th>
              <th className="py-2 pr-3">Enabled</th>
              <th className="py-2 pr-3">Priority</th>
              <th className="py-2 pr-3">Test</th>
              <th className="py-2 pr-3">Mappings</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => {
              const res = testResult[p.id];
              const busy = testBusy[p.id] ?? false;
              const isExpanded = expandedId === p.id;
              return (
                <Fragment key={p.id}>
                  <tr
                    data-testid={`provider-row-${p.name}`}
                    className="border-b border-md-sys-color-outline-variant/50"
                  >
                    <td className="py-2 pr-3 font-medium">{p.name}</td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {p.server_uris.join(", ")}
                    </td>
                    <td className="py-2 pr-3">
                      {p.enabled ? (
                        <span className="rounded-full bg-md-sys-color-surface-container px-2 py-0.5 text-xs text-md-sys-color-on-surface-variant">
                          Yes
                        </span>
                      ) : (
                        <span className="rounded-full bg-severity-4/20 px-2 py-0.5 text-xs text-severity-4">
                          No
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-xs">{p.priority}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container disabled:opacity-50"
                          onClick={() => {
                            void runTest(p);
                          }}
                          aria-label={`Test connection for ${p.name}`}
                        >
                          {busy ? "Testing…" : "Test"}
                        </button>
                        {res !== undefined && (
                          <span
                            data-testid={`test-result-${p.name}`}
                            className={
                              res.ok
                                ? "text-xs text-green-500"
                                : "text-xs text-severity-4"
                            }
                          >
                            {res.ok
                              ? `OK (${res.duration_ms}ms)`
                              : `Error: ${res.error ?? "unknown"}`}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2 pr-3">
                      <button
                        type="button"
                        className="text-xs text-md-sys-color-primary underline hover:opacity-80"
                        onClick={() => toggleExpand(p.id)}
                        aria-expanded={isExpanded}
                        aria-label={`Mappings for ${p.name}`}
                      >
                        {isExpanded ? "Hide" : "Mappings"}
                      </button>
                    </td>
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                          onClick={() => setEditing(p)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="rounded-full border border-severity-4/40 px-3 py-0.5 text-xs text-severity-4 hover:bg-severity-4/10"
                          onClick={() => {
                            void softDelete(p);
                          }}
                          aria-label={`Delete ${p.name}`}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr
                      className="border-b border-md-sys-color-outline-variant/30"
                    >
                      <td colSpan={7} className="bg-md-sys-color-surface-container/30 px-4 pb-3">
                        <MappingsTable
                          provider={p}
                          mappings={mappings[p.id] ?? []}
                          onRefresh={() => refreshMappings(p.id)}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}

      {editing !== null && (
        <ProviderDrawer
          provider={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Edit drawer (Create or Update)
// ---------------------------------------------------------------------------

interface ProviderDrawerProps {
  provider: LdapProvider | null; // null = new
  onClose: () => void;
  onSaved: () => Promise<void>;
}

function ProviderDrawer({ provider, onClose, onSaved }: ProviderDrawerProps) {
  const { apiCall } = useAuth();

  const [name, setName] = useState(provider?.name ?? "");
  const [serverUris, setServerUris] = useState(provider?.server_uris.join("\n") ?? "");
  const [bindDn, setBindDn] = useState(provider?.bind_dn ?? "");
  const [bindPassword, setBindPassword] = useState(""); // never preloaded
  const [baseDn, setBaseDn] = useState(provider?.base_dn ?? "");
  const [enabled, setEnabled] = useState(provider?.enabled ?? true);
  const [priority, setPriority] = useState(provider?.priority ?? 10);
  const [tlsRequired, setTlsRequired] = useState(provider?.tls_required ?? true);
  const [allowInsecure, setAllowInsecure] = useState(provider?.allow_insecure ?? false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNew = provider === null;

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const uris = serverUris
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      if (isNew) {
        await apiCall<LdapProvider>("/v1/admin/ldap-providers", {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            server_uris: uris,
            bind_dn: bindDn.trim(),
            bind_password: bindPassword,
            base_dn: baseDn.trim(),
            enabled,
            priority,
            tls_required: tlsRequired,
            allow_insecure: allowInsecure,
          }),
        });
      } else {
        const patch: Record<string, unknown> = {
          name: name.trim(),
          server_uris: uris,
          bind_dn: bindDn.trim(),
          base_dn: baseDn.trim(),
          enabled,
          priority,
          tls_required: tlsRequired,
          allow_insecure: allowInsecure,
        };
        // Only include bind_password when the user actually typed something
        if (bindPassword.length > 0) {
          patch.bind_password = bindPassword;
        }
        await apiCall<LdapProvider>(`/v1/admin/ldap-providers/${provider.id}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
      }
      await onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    "w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-md-sys-color-primary";
  const labelCls = "block text-xs text-md-sys-color-on-surface-variant mb-0.5";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/30"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={isNew ? "Add LDAP provider" : `Edit ${provider.name}`}
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-md-sys-color-surface shadow-xl"
        data-testid="provider-drawer"
      >
        <div className="flex items-center justify-between border-b border-md-sys-color-outline-variant p-4">
          <h2 className="text-lg font-semibold">
            {isNew ? "Add LDAP Provider" : `Edit: ${provider.name}`}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-md-sys-color-on-surface-variant hover:text-md-sys-color-on-surface"
            aria-label="Close drawer"
          >
            <span aria-hidden className="material-symbols-rounded text-[20px]">
              close
            </span>
          </button>
        </div>

        <div className="flex-1 space-y-4 p-4">
          {error && (
            <p role="alert" className="rounded bg-severity-4/20 p-2 text-xs text-severity-4">
              {error}
            </p>
          )}

          <div>
            <label htmlFor="ldap-name" className={labelCls}>
              Name *
            </label>
            <input
              id="ldap-name"
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="corp-ad"
            />
          </div>

          <div>
            <label htmlFor="ldap-server-uris" className={labelCls}>
              Server URIs (one per line) *
            </label>
            <textarea
              id="ldap-server-uris"
              className={inputCls}
              rows={3}
              value={serverUris}
              onChange={(e) => setServerUris(e.target.value)}
              placeholder={"ldaps://dc01.corp.com:636\nldaps://dc02.corp.com:636"}
            />
          </div>

          <div>
            <label htmlFor="ldap-bind-dn" className={labelCls}>
              Bind DN *
            </label>
            <input
              id="ldap-bind-dn"
              className={inputCls}
              value={bindDn}
              onChange={(e) => setBindDn(e.target.value)}
              placeholder="cn=svc-adhkar,ou=service,dc=corp,dc=com"
            />
          </div>

          <div>
            <label htmlFor="ldap-bind-password" className={labelCls}>
              Bind password {isNew ? "*" : "(leave blank to keep current)"}
            </label>
            <input
              id="ldap-bind-password"
              type="password"
              autoComplete="new-password"
              className={inputCls}
              value={bindPassword}
              onChange={(e) => setBindPassword(e.target.value)}
              placeholder={isNew ? "••••••••" : "••••••••  (not changed)"}
            />
          </div>

          <div>
            <label htmlFor="ldap-base-dn" className={labelCls}>
              Base DN *
            </label>
            <input
              id="ldap-base-dn"
              className={inputCls}
              value={baseDn}
              onChange={(e) => setBaseDn(e.target.value)}
              placeholder="dc=corp,dc=com"
            />
          </div>

          <div>
            <label htmlFor="ldap-priority" className={labelCls}>
              Priority
            </label>
            <input
              id="ldap-priority"
              type="number"
              min={0}
              className={inputCls}
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
            />
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="h-4 w-4 rounded"
              />
              Enabled
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={tlsRequired}
                onChange={(e) => setTlsRequired(e.target.checked)}
                className="h-4 w-4 rounded"
              />
              TLS required (StartTLS / LDAPS)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={allowInsecure}
                onChange={(e) => setAllowInsecure(e.target.checked)}
                className="h-4 w-4 rounded"
              />
              Allow insecure (plain LDAP)
            </label>
          </div>
        </div>

        <div className="flex gap-2 border-t border-md-sys-color-outline-variant p-4">
          <button
            type="button"
            disabled={busy || !name.trim() || !baseDn.trim() || !serverUris.trim()}
            className="rounded-full bg-md-sys-color-primary px-4 py-1.5 text-sm font-medium text-md-sys-color-on-primary hover:brightness-110 disabled:opacity-50"
            onClick={() => {
              void save();
            }}
          >
            {busy ? "Saving…" : isNew ? "Create" : "Save"}
          </button>
          <button
            type="button"
            className="rounded-full border border-md-sys-color-outline-variant px-4 py-1.5 text-sm hover:bg-md-sys-color-surface-container"
            onClick={onClose}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mappings table (per provider, shown inline when expanded)
// ---------------------------------------------------------------------------

interface MappingsTableProps {
  provider: LdapProvider;
  mappings: LdapGroupMapping[];
  onRefresh: () => Promise<void>;
}

function MappingsTable({ provider, mappings, onRefresh }: MappingsTableProps) {
  const { apiCall } = useAuth();

  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  const [profiles, setProfiles] = useState<ProfileRow[]>([]);
  const [addGroupDn, setAddGroupDn] = useState("");
  const [addOrgId, setAddOrgId] = useState("");
  const [addProfileId, setAddProfileId] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiCall<OrgRow[]>("/v1/organizations")
      .then(setOrgs)
      .catch(() => undefined);
    void apiCall<ProfileRow[]>("/v1/profiles")
      .then(setProfiles)
      .catch(() => undefined);
  }, [apiCall]);

  const addMapping = async () => {
    if (!addGroupDn.trim() || !addOrgId || !addProfileId) return;
    setAddBusy(true);
    setError(null);
    try {
      await apiCall(`/v1/admin/ldap-providers/${provider.id}/mappings`, {
        method: "POST",
        body: JSON.stringify({
          group_dn: addGroupDn.trim(),
          organization_id: addOrgId,
          profile_id: addProfileId,
        }),
      });
      setAddGroupDn("");
      setAddOrgId("");
      setAddProfileId("");
      await onRefresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAddBusy(false);
    }
  };

  const deleteMapping = async (mappingId: string) => {
    try {
      await apiCall(
        `/v1/admin/ldap-providers/${provider.id}/mappings/${mappingId}`,
        { method: "DELETE" },
      );
      await onRefresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const inputCls =
    "rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-xs";

  return (
    <div className="mt-3 space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-md-sys-color-on-surface-variant">
        Group Mappings — {provider.name}
      </h3>

      {error && (
        <p role="alert" className="text-xs text-severity-4">
          {error}
        </p>
      )}

      {mappings.length === 0 ? (
        <p className="text-xs text-md-sys-color-on-surface-variant">No mappings yet.</p>
      ) : (
        <table className="w-full table-auto border-collapse text-xs">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant/50 text-left text-md-sys-color-on-surface-variant">
              <th className="py-1 pr-3">Group DN</th>
              <th className="py-1 pr-3">Organization</th>
              <th className="py-1 pr-3">Profile</th>
              <th className="py-1" />
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => (
              <tr
                key={m.id}
                data-testid={`mapping-row-${m.id}`}
                className="border-b border-md-sys-color-outline-variant/30"
              >
                <td className="py-1 pr-3 font-mono">{m.group_dn}</td>
                <td className="py-1 pr-3">
                  {orgs.find((o) => o.id === m.organization_id)?.name ?? m.organization_id}
                </td>
                <td className="py-1 pr-3">
                  {profiles.find((pr) => pr.id === m.profile_id)?.name ?? m.profile_id}
                </td>
                <td className="py-1">
                  <button
                    type="button"
                    className="text-xs text-severity-4 hover:underline"
                    aria-label={`Delete mapping ${m.group_dn}`}
                    onClick={() => {
                      void deleteMapping(m.id);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div
        className="flex flex-wrap items-end gap-2 rounded border border-dashed border-md-sys-color-outline-variant p-2"
        data-testid="add-mapping-form"
      >
        <div>
          <label className="block text-[10px] text-md-sys-color-on-surface-variant mb-0.5">
            Group DN
          </label>
          <input
            className={inputCls}
            value={addGroupDn}
            onChange={(e) => setAddGroupDn(e.target.value)}
            placeholder="CN=IR-Analysts,OU=Groups,DC=corp,DC=com"
            style={{ minWidth: "260px" }}
            aria-label="Group DN"
          />
        </div>
        <div>
          <label className="block text-[10px] text-md-sys-color-on-surface-variant mb-0.5">
            Organization
          </label>
          <select
            className={inputCls}
            value={addOrgId}
            onChange={(e) => setAddOrgId(e.target.value)}
            aria-label="Organization"
          >
            <option value="">— select —</option>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[10px] text-md-sys-color-on-surface-variant mb-0.5">
            Profile
          </label>
          <select
            className={inputCls}
            value={addProfileId}
            onChange={(e) => setAddProfileId(e.target.value)}
            aria-label="Profile"
          >
            <option value="">— select —</option>
            {profiles.map((pr) => (
              <option key={pr.id} value={pr.id}>
                {pr.name}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          disabled={addBusy || !addGroupDn.trim() || !addOrgId || !addProfileId}
          className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary hover:brightness-110 disabled:opacity-50"
          onClick={() => {
            void addMapping();
          }}
          aria-label="Add mapping"
        >
          {addBusy ? "Adding…" : "Add"}
        </button>
      </div>
    </div>
  );
}
