/**
 * Admin: Users management (Phase 1a UI gap). List + invite + lock/unlock.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

interface UserRow {
  id: string;
  email: string;
  display_name: string;
  is_locked: boolean;
  current_org_id: string | null;
  created_at: string;
}

interface InviteResponse {
  user_id: string;
  invite_url: string;
}

export function AdminUsersPage() {
  const { apiCall, permissions } = useAuth();
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [lastInvite, setLastInvite] = useState<InviteResponse | null>(null);

  const [sortRecent, setSortRecent] = useState(false);

  const canManage = permissions.has("manageUser");

  const refresh = async () => {
    try {
      const rows = await apiCall<UserRow[]>(
        sortRecent ? "/v1/users/recent?limit=50" : "/v1/users",
      );
      setUsers(rows);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall, sortRecent]);

  const invite = async () => {
    if (!inviteEmail.trim()) return;
    setInviteBusy(true);
    try {
      const r = await apiCall<InviteResponse>("/v1/users/invite", {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail.trim(),
          display_name: inviteName.trim() || inviteEmail.trim(),
        }),
      });
      setLastInvite(r);
      setInviteEmail("");
      setInviteName("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setInviteBusy(false);
    }
  };

  const toggleLock = async (u: UserRow) => {
    try {
      await apiCall(`/v1/users/${u.id}/${u.is_locked ? "unlock" : "lock"}`, {
        method: "POST",
        body: "{}",
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
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
  if (users === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Users</h1>

      {canManage ? (
        <article className="rounded border border-md-sys-color-outline-variant p-3">
          <h2 className="mb-2 text-sm font-medium">Invite user</h2>
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="email@org"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <input
              className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1 text-sm"
              placeholder="Display name"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
            />
            <button
              type="button"
              className="rounded-full bg-md-sys-color-primary px-3 py-1 text-xs text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void invite();
              }}
              disabled={inviteBusy || !inviteEmail.trim()}
            >
              {inviteBusy ? "Inviting…" : "Send invite"}
            </button>
          </div>
          {lastInvite ? (
            <p className="mt-2 break-all text-xs text-md-sys-color-on-surface-variant">
              Invite URL: <span className="font-mono">{lastInvite.invite_url}</span>
            </p>
          ) : null}
        </article>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setSortRecent((v) => !v)}
          className={
            "rounded-full px-3 py-1 text-xs " +
            (sortRecent
              ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
              : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container")
          }
          title="Toggle ordering by most-recent audit-log activity"
        >
          {sortRecent ? "Sorted by recent activity ✓" : "Sort by recent activity"}
        </button>
      </div>

      <table className="w-full table-auto border-collapse text-sm">
        <thead>
          <tr className="border-b border-md-sys-color-outline-variant text-left">
            <th className="py-2 pr-3">Email</th>
            <th className="py-2 pr-3">Name</th>
            <th className="py-2 pr-3">Status</th>
            <th className="py-2 pr-3" />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr
              key={u.id}
              className="border-b border-md-sys-color-outline-variant/50"
            >
              <td className="py-2 pr-3 font-mono text-xs">{u.email}</td>
              <td className="py-2 pr-3">{u.display_name}</td>
              <td className="py-2 pr-3">
                {u.is_locked ? (
                  <span className="rounded-full bg-severity-3/20 px-2 py-0.5 text-xs text-severity-3">
                    locked
                  </span>
                ) : (
                  <span className="text-xs text-md-sys-color-on-surface-variant">
                    active
                  </span>
                )}
              </td>
              <td className="py-2 pr-3">
                {canManage ? (
                  <button
                    type="button"
                    className="rounded-full border border-md-sys-color-outline-variant px-3 py-0.5 text-xs hover:bg-md-sys-color-surface-container"
                    onClick={() => {
                      void toggleLock(u);
                    }}
                  >
                    {u.is_locked ? "Unlock" : "Lock"}
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
