import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";

import { CasesPage } from "@/pages/CasesPage";
import { HealthPage } from "@/pages/HealthPage";
import { LoginPage } from "@/pages/LoginPage";

import { AppShell } from "./AppShell";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});

const protectedLayout = createRoute({
  getParentRoute: () => rootRoute,
  id: "protected",
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
  beforeLoad: ({ context }) => {
    // Auth gate is enforced in main page components via useAuth() effect.
    // The AppShell layout assumes a logged-in user; if not, components
    // redirect via useAuth.
    void context;
  },
});

const indexRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/",
  component: HealthPage,
});

const healthRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/health",
  component: HealthPage,
});

const casesRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/cases",
  component: CasesPage,
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    loginRoute,
    protectedLayout.addChildren([indexRoute, healthRoute, casesRoute]),
  ]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

// silence unused 'redirect' if not invoked here
void redirect;
