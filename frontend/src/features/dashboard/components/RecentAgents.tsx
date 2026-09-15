import { Bot } from 'lucide-react';
import { Link } from 'react-router';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { AgentStatusBadge, RiskBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { Card, CardHeader } from '@/components/ui/Card';
import { useAgents } from '@/features/agents/api';
import { formatRelative } from '@/lib/format';

export function RecentAgents() {
  const query = useAgents({ sort: 'last_execution_desc' });
  return (
    <Card>
      <CardHeader
        title="Recently used agents"
        description="Agents ordered by their last execution (demo)."
        action={
          <Link to="/agents" className="text-sm font-medium text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
            All agents
          </Link>
        }
      />
      <div className="p-4">
        <QueryState
          query={query}
          loading={<LoadingState variant="cards" label="Loading agents…" />}
          errorTitle="Agents unavailable"
          isEmpty={(agents) => agents.length === 0}
          empty={<EmptyState icon={Bot} title="No agents yet" description="Create an agent to see it here." />}
        >
          {(agents) => (
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {agents.slice(0, 4).map((agent) => (
                <li key={agent.id} className="relative rounded-lg border border-line p-4 transition-colors hover:border-line-strong">
                  <div className="flex items-start gap-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-md bg-brand-soft text-brand-strong">
                      <Bot aria-hidden="true" className="size-4" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold text-fg">
                        <Link to={`/agents/${agent.id}`} className="after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-ring">
                          {agent.name}
                        </Link>
                      </h3>
                      <p className="text-xs text-fg-muted">{CATEGORY_LABELS[agent.category]}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <AgentStatusBadge status={agent.status} />
                    <RiskBadge level={agent.riskLevel} />
                  </div>
                  <p className="mt-3 text-xs text-fg-subtle">
                    Last run {agent.lastExecutionAt ? formatRelative(agent.lastExecutionAt) : 'never'}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      </div>
    </Card>
  );
}
