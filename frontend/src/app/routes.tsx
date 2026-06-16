import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";

import { AdhkarMindPage } from "@/pages/AdhkarMindPage";
import { AdminProfilesPage } from "@/pages/AdminProfilesPage";
import { AdminUsersPage } from "@/pages/AdminUsersPage";
import { AnalyzerJobsPage } from "@/pages/AnalyzerJobsPage";
import { AttackHeatmapPage } from "@/pages/AttackHeatmapPage";
import { AuditLogPage } from "@/pages/AuditLogPage";
import { AlertDetailPage } from "@/pages/AlertDetailPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { CaseDetailPage } from "@/pages/CaseDetailPage";
import { CaseTemplatesPage } from "@/pages/CaseTemplatesPage";
import { GdprPage } from "@/pages/GdprPage";
import { PortalPage } from "@/pages/PortalPage";
import { SearchPage } from "@/pages/SearchPage";
import { TasksPage } from "@/pages/TasksPage";
import { TaxonomiesPage } from "@/pages/TaxonomiesPage";
import { CasesPage } from "@/pages/CasesPage";
import { CreateCasePage } from "@/pages/CreateCasePage";
import { HealthPage } from "@/pages/HealthPage";
import { KnowledgeBasePage } from "@/pages/KnowledgeBasePage";
import { LoginPage } from "@/pages/LoginPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { ObservableDetailPage } from "@/pages/ObservableDetailPage";
import { ObservablesPage } from "@/pages/ObservablesPage";
import { TtpsPage } from "@/pages/TtpsPage";

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

const alertDetailRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/alerts/$alertId",
  component: function AlertDetailRouteView() {
    const { alertId } = alertDetailRoute.useParams();
    return <AlertDetailPage alertId={alertId} />;
  },
});

const observablesRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/observables",
  component: ObservablesPage,
});

const observableDetailRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/observables/$observableId",
  component: function ObservableDetailRouteView() {
    const { observableId } = observableDetailRoute.useParams();
    return <ObservableDetailPage observableId={observableId} />;
  },
});

const mindRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/adhkar-mind",
  component: AdhkarMindPage,
});

const kbRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/knowledge-base",
  component: KnowledgeBasePage,
});

const dashboardRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/dashboard",
  component: DashboardPage,
});

const notificationsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/notifications",
  component: NotificationsPage,
});

const ttpsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/ttps",
  component: TtpsPage,
});

const adminUsersRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/admin/users",
  component: AdminUsersPage,
});

const adminProfilesRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/admin/profiles",
  component: AdminProfilesPage,
});

const caseTemplatesRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/case-templates",
  component: CaseTemplatesPage,
});

const gdprRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/admin/gdpr",
  component: GdprPage,
});

const portalRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/portal",
  component: PortalPage,
});

const searchRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/search",
  component: SearchPage,
});

const auditRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/admin/audit",
  component: AuditLogPage,
});

const analyzerJobsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/analyzer-jobs",
  component: AnalyzerJobsPage,
});

const tasksRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/tasks",
  component: TasksPage,
});

const taxonomiesRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/admin/taxonomies",
  component: TaxonomiesPage,
});

const attackHeatmapRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: "/attack-heatmap",
  component: AttackHeatmapPage,
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
      alertDetailRoute,
      observablesRoute,
      observableDetailRoute,
      mindRoute,
      kbRoute,
      dashboardRoute,
      notificationsRoute,
      ttpsRoute,
      adminUsersRoute,
      adminProfilesRoute,
      caseTemplatesRoute,
      gdprRoute,
      portalRoute,
      searchRoute,
      auditRoute,
      analyzerJobsRoute,
      tasksRoute,
      taxonomiesRoute,
      attackHeatmapRoute,
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
