import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

// Stub TanStack Router primitives used by the shell at module-resolution time.
vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...rest }: { to: string; children: React.ReactNode }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  ),
  useNavigate: () => () => undefined,
}));

import { AppShell } from "./AppShell";

describe("<AppShell>", () => {
  it("renders TopAppBar with product name and ⌘K trigger", () => {
    render(
      <AppShell>
        <div>page</div>
      </AppShell>,
    );
    expect(screen.getByText("ADHKAR")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open command palette/i })).toBeInTheDocument();
    expect(screen.getByText("page")).toBeInTheDocument();
  });

  it("NavigationDrawer shows Health enabled and other items disabled with tooltip", () => {
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    const health = screen.getByRole("link", { name: /health/i });
    expect(health).toBeInTheDocument();
    const cases = screen.getByRole("button", { name: /cases/i });
    expect(cases).toBeDisabled();
    expect(cases).toHaveAttribute("title", expect.stringContaining("Phase"));
  });

  it("⌘K opens the command palette", async () => {
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    await userEvent.keyboard("{Meta>}k{/Meta}");
    expect(screen.getByRole("dialog", { name: /command palette/i })).toBeInTheDocument();
    expect(screen.getByText(/Go to Health/i)).toBeInTheDocument();
  });

  it("theme toggle flips data-theme", async () => {
    document.documentElement.dataset.theme = "dark";
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    await userEvent.click(screen.getByRole("button", { name: /toggle theme/i }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
