import { Activity, CircleCheck, Coins, Timer } from 'lucide-react';
import { BarChart } from '@/components/charts/BarChart';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { PageHeader } from '@/components/layout/PageHeader';
import { ExecutionStatusBadge } from '@/components/status/StatusBadges';
import { Card, CardHeader } from '@/components/ui/Card';
import { Meter } from '@/components/ui/Meter';
import { StatCard } from '@/components/ui/StatCard';
import { formatCompact, formatDuration, formatNumber } from '@/lib/format';
import { EXECUTION_STATUSES } from '@/types/domain';
import { useAnalyticsSummary } from './api';

const dayLabel = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' });

export default function AnalyticsPage() {
  const query = useAnalyticsSummary();
  return (
    <>
      <PageHeader title="Analytics" description="Execution volume, outcomes and token usage over the last 14 days." />
      <DataNotice
        resource="analytics"
        className="mb-6"
        demo="Analytics are computed from demonstration data. They are not real usage statistics."
        live="Computed from your organization's runs and recorded model usage. Cost is an estimate from published prices, not a bill."
      />

      <QueryState query={query} loading={<LoadingState label="Loading analytics…" />} errorTitle="Analytics could not be loaded">
        {(data) => {
          const totalExecutions = EXECUTION_STATUSES.reduce((sum, s) => sum + data.statusBreakdown[s], 0);
          const tokens14d = data.tokensPerDay.reduce((sum, d) => sum + d.value, 0);
          return (
            <>
              <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Success rate" value={`${Math.round(data.successRate * 100)}%`} icon={CircleCheck} tone="success" description="Of finished executions" />
                <StatCard label="Average duration" value={formatDuration(data.averageDurationMs)} icon={Timer} tone="info" />
                <StatCard label="Executions tracked" value={formatNumber(totalExecutions)} icon={Activity} tone="brand" />
                <StatCard
                  label="Tokens (14 days)"
                  value={formatCompact(tokens14d)}
                  icon={Coins}
                  tone="warning"
                  description={data.estimatedCostUsd === undefined ? undefined : `About $${data.estimatedCostUsd.toFixed(2)} estimated`}
                />
              </section>

              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader title="Executions per day" />
                  <div className="px-5 py-4">
                    <BarChart title="Executions per day, last 14 days" data={data.executionsPerDay.map((d) => ({ label: dayLabel.format(new Date(d.date)), value: d.value }))} formatValue={formatNumber} />
                  </div>
                </Card>
                <Card>
                  <CardHeader title="Tokens per day" />
                  <div className="px-5 py-4">
                    <BarChart title="Tokens per day, last 14 days" data={data.tokensPerDay.map((d) => ({ label: dayLabel.format(new Date(d.date)), value: d.value }))} formatValue={formatCompact} />
                  </div>
                </Card>
              </div>

              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader title="Status breakdown" />
                  <ul className="space-y-3 px-5 py-4">
                    {EXECUTION_STATUSES.map((status) => (
                      <li key={status} className="grid grid-cols-[9rem_minmax(0,1fr)_2.5rem] items-center gap-3">
                        <ExecutionStatusBadge status={status} />
                        <Meter value={data.statusBreakdown[status]} max={Math.max(1, totalExecutions)} label={`${status} executions`} valueText={`${data.statusBreakdown[status]} of ${totalExecutions}`} />
                        <span className="text-right text-sm text-fg-muted tabular-nums">{data.statusBreakdown[status]}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
                <Card>
                  <CardHeader title="Most executed agents" />
                  <ol className="divide-y divide-line px-5">
                    {data.topAgents.map((agent, index) => (
                      <li key={agent.agentId} className="flex items-center justify-between gap-3 py-3">
                        <span className="text-sm text-fg">
                          <span className="mr-2 text-fg-subtle tabular-nums">{index + 1}.</span>
                          {agent.name}
                        </span>
                        <span className="text-sm text-fg-muted tabular-nums">{agent.executions} runs</span>
                      </li>
                    ))}
                  </ol>
                </Card>
              </div>
            </>
          );
        }}
      </QueryState>
    </>
  );
}
