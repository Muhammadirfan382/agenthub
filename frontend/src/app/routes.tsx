import { lazy } from 'react';
import { Navigate, type RouteObject } from 'react-router';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAuth } from '@/features/auth/RequireAuth';
import NotFoundPage from '@/features/errors/NotFoundPage';
import RouteErrorPage from '@/features/errors/RouteErrorPage';

// Pages are code-split; AppShell's Suspense boundary shows the route loading state.
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'));
const AgentsPage = lazy(() => import('@/features/agents/AgentsPage'));
const AgentDetailPage = lazy(() => import('@/features/agents/AgentDetailPage'));
const CreateAgentPage = lazy(() => import('@/features/agents/CreateAgentPage'));
const EditAgentPage = lazy(() => import('@/features/agents/EditAgentPage'));
const MarketplacePage = lazy(() => import('@/features/marketplace/MarketplacePage'));
const ExecutionsPage = lazy(() => import('@/features/executions/ExecutionsPage'));
const ExecutionDetailPage = lazy(() => import('@/features/executions/ExecutionDetailPage'));
const SecurityPage = lazy(() => import('@/features/security/SecurityPage'));
const AnalyticsPage = lazy(() => import('@/features/analytics/AnalyticsPage'));
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'));
const LoginPage = lazy(() => import('@/features/auth/LoginPage'));

export const routes: RouteObject[] = [
  {
    // Outside the shell: the only route reachable without a session.
    path: '/login',
    element: <LoginPage />,
    errorElement: <RouteErrorPage />,
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    // Last-resort boundary if the shell itself fails.
    errorElement: <RouteErrorPage />,
    children: [
      {
        // Page-level boundary: keeps the shell visible when a page throws.
        errorElement: <RouteErrorPage />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'agents', element: <AgentsPage /> },
          { path: 'agents/create', element: <CreateAgentPage /> },
          { path: 'agents/:id', element: <AgentDetailPage /> },
          { path: 'agents/:id/edit', element: <EditAgentPage /> },
          { path: 'marketplace', element: <MarketplacePage /> },
          { path: 'executions', element: <ExecutionsPage /> },
          { path: 'executions/:id', element: <ExecutionDetailPage /> },
          { path: 'security', element: <SecurityPage /> },
          { path: 'analytics', element: <AnalyticsPage /> },
          { path: 'settings', element: <SettingsPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];
