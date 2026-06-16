import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";

import { AdhkarMindPage } from "@/pages/AdhkarMindPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { CaseDetailPage } from "@/pages/CaseDetailPage";
import { CasesPage } from "@/pages/CasesPage";
import { CreateCasePage } from "@/pages/CreateCasePage";
import { HealthPage } from "@/pages/HealthPage";
import { LoginPage } from "@/pages/LoginPage";
import { ObservablesPage } from "@/pages/ObservablesPage";

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

const createCaseRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/cases/new",
  component: CreateCasePage,
});

const alertsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/alerts",
  component: AlertsPage,
});

const observablesRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/observables",
  component: ObservablesPage,
});

const mindRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/adhkar-mind",
  component: AdhkarMindPage,
});

const caseDetailRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/cases/$caseId",
  component: function CaseDetailRouteView() {
    const { caseId } = caseDetailRoute.useParams();
    return <CaseDetailPage caseId={caseId} />;
  },
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    loginRoute,
    protectedLayout.addChildren([
      indexRoute,
      healthRoute,
      casesRoute,
      createCaseRoute,
      caseDetailRoute,
      alertsRoute,
      observablesRoute,
      mindRoute,
    ]),
  ]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

// silence unused 'redirect' if not invoked here
void redirect;
