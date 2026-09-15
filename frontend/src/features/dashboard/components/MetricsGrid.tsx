import { Activity, Bot, CircleCheck, CircleX, Power, ShieldAlert } from 'lucide-react';
import { ErrorState } from '@/components/feedback/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatCard } from '@/components/ui/StatCard';
import { formatNumber } from '@/lib/format';
import { useDashboardSummary } from '../api';

export function MetricsGrid() {
  const query = useDashboardSummary();

  if (query.isPending) {
    return (
      <div role="status" aria-live="polite" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <span className="sr-only">Loading metrics…</span>
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-28 rounded-lg" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return <ErrorState title="Metrics unavailable" onRetry={() => void query.refetch()} retrying={query.isFetching} />;
  }

  const s = query.data;
  return (
    <section aria-label="Overview metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
      <StatCard label="Total agents" value={formatNumber(s.totalAgents)} icon={Bot} tone="brand" to="/agents" />
      <StatCard label="Active agents" value={formatNumber(s.activeAgents)} icon={Power} tone="success" to="/agents" />
      <StatCard label="Running executions" value={formatNumber(s.runningExecutions)} icon={Activity} tone="info" to="/executions" />
      <StatCard label="Completed executions" value={formatNumber(s.completedExecutions)} icon={CircleCheck} tone="success" to="/executions" />
      <StatCard label="Failed executions" value={formatNumber(s.failedExecutions)} icon={CircleX} tone="danger" description="Includes timeouts" to="/executions" />
      <StatCard label="Security alerts" value={formatNumber(s.securityAlerts)} icon={ShieldAlert} tone="warning" description="Open or investigating" to="/security" />
    </section>
  );
}
