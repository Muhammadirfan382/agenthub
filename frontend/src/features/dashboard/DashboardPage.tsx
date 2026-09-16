import { Activity, Plus } from 'lucide-react';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { PageHeader } from '@/components/layout/PageHeader';
import { useAgentPermissions } from '@/features/agents/permissions';
import { LinkButton } from '@/components/ui/Button';
import { MetricsGrid } from './components/MetricsGrid';
import { RecentActivity } from './components/RecentActivity';
import { RecentAgents } from './components/RecentAgents';
import { SystemStatusCard } from './components/SystemStatusCard';

export default function DashboardPage() {
  const { canCreate } = useAgentPermissions();

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Your agents, their executions and the platform's security posture at a glance."
        actions={
          <>
            <LinkButton to="/executions" variant="secondary" size="sm">
              <Activity aria-hidden="true" className="size-4" />
              View executions
            </LinkButton>
            {canCreate && (
              <LinkButton to="/agents/create" variant="primary" size="sm">
                <Plus aria-hidden="true" className="size-4" />
                Create agent
              </LinkButton>
            )}
          </>
        }
      />

      <DataNotice
        resource="dashboard"
        className="mb-6"
        demo="Metrics, activity and system status on this page are demonstration data. They do not reflect a real backend, real agents or real executions."
        live="Agent and execution counts come from the backend. Recent activity, system status and security figures on this page are still demonstration data."
      />

      <MetricsGrid />

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <RecentActivity />
        </div>
        <SystemStatusCard />
      </div>

      <div className="mt-6">
        <RecentAgents />
      </div>
    </>
  );
}
