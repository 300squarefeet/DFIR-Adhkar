import { useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

import { Button } from "@/design-system/components/Button";
import { useAuth } from "@/lib/auth";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password, needMfa ? mfaCode : undefined);
      navigate({ to: "/" });
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("mfa")) {
        setNeedMfa(true);
        setError("MFA code required.");
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-surface">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-shape-large border border-outline-variant bg-surface-container p-6"
      >
        <h1 className="mb-4 text-lg font-semibold text-on-surface">Sign in to Adhkar</h1>
        <label className="mb-2 block text-sm text-on-surface-variant">
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-shape-small border border-outline-variant bg-surface-container-low p-2 text-sm text-on-surface outline-none focus:border-primary"
          />
        </label>
        <label className="mb-2 block text-sm text-on-surface-variant">
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-shape-small border border-outline-variant bg-surface-container-low p-2 text-sm text-on-surface outline-none focus:border-primary"
          />
        </label>
        {needMfa && (
          <label className="mb-2 block text-sm text-on-surface-variant">
            MFA code
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              required
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              className="mt-1 w-full rounded-shape-small border border-outline-variant bg-surface-container-low p-2 text-sm text-on-surface outline-none focus:border-primary"
            />
          </label>
        )}
        {error && (
          <p role="alert" className="my-2 text-xs text-error">
            {error}
          </p>
        )}
        <Button type="submit" variant="filled" size="md" loading={busy} className="mt-4 w-full">
          Sign in
        </Button>
      </form>
    </div>
  );
}
