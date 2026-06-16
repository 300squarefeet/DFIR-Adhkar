/**
 * User menu — displays current user/org and lets them switch orgs or sign
 * out. Mounts in TopAppBar.
 */

import { useContext, useEffect, useRef, useState } from "react";

import { AuthContext } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface SwitchOrgResponse {
  access_token: string;
  current_org_id: string | null;
}

export function UserMenu() {
  // Optional context: tests mount TopAppBar without AuthProvider.
  const ctx = useContext(AuthContext);
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!wrapper.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  if (!ctx || !ctx.user)
    return <span className="text-xs text-on-surface-variant">@guest</span>;
  const { user, logout, apiCall } = ctx;

  const current = user.memberships.find((m) => m.org_id === user.current_org_id);
  const others = user.memberships.filter((m) => m.org_id !== user.current_org_id);

  const switchTo = async (orgId: string) => {
    try {
      await apiCall<SwitchOrgResponse>("/v1/auth/switch-org", {
        method: "POST",
        body: JSON.stringify({ org_id: orgId }),
      });
      toast.success("Switched org. Reloading…");
      // Force a clean re-load so cached query state flushes.
      window.location.reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="relative" ref={wrapper}>
      <button
        type="button"
        className="flex items-center gap-2 rounded-shape-medium px-2 py-1 text-xs text-on-surface hover:bg-surface-container-high"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span aria-hidden className="material-symbols-rounded text-[16px]">
          account_circle
        </span>
        <span className="font-medium">{user.display_name}</span>
        {current ? (
          <span className="text-on-surface-variant">· {current.org_name}</span>
        ) : null}
        <span aria-hidden className="material-symbols-rounded text-[14px]">
          arrow_drop_down
        </span>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 w-64 rounded-shape-medium border border-outline-variant bg-surface-container p-1 text-sm shadow"
        >
          <div className="px-3 py-2 text-xs text-on-surface-variant">
            <div>Signed in as</div>
            <div className="font-mono text-on-surface">{user.email}</div>
          </div>
          {others.length > 0 ? (
            <>
              <div className="border-t border-outline-variant px-3 pb-1 pt-2 text-[10px] uppercase text-on-surface-variant">
                Switch organization
              </div>
              <ul>
                {others.map((m) => (
                  <li key={m.org_id}>
                    <button
                      type="button"
                      onClick={() => {
                        void switchTo(m.org_id);
                      }}
                      className="block w-full rounded px-3 py-1 text-left hover:bg-surface-container-high"
                    >
                      <span>{m.org_name}</span>
                      <span className="ml-2 text-xs text-on-surface-variant">
                        {m.profile_name}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <div className="mt-1 border-t border-outline-variant">
            <button
              type="button"
              onClick={() => {
                void logout();
              }}
              className="block w-full rounded px-3 py-1 text-left text-error hover:bg-error/10"
            >
              Sign out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
