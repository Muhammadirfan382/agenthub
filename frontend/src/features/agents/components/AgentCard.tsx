import { Bot } from 'lucide-react';
import { Link } from 'react-router';
import { AgentStatusBadge, RiskBadge, VerificationBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { formatDate } from '@/lib/format';
import type { Agent } from '@/types/domain';
import { AgentActionsMenu } from './AgentActionsMenu';

interface AgentCardProps {
  agent: Agent;
  onExecute: (agent: Agent) => void;
  onDelete: (agent: Agent) => void;
}

export function AgentCard({ agent, onExecute, onDelete }: AgentCardProps) {
  return (
    <article className="flex h-full flex-col rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-md bg-brand-soft text-brand-strong">
          <Bot aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold text-fg">
            <Link to={`/agents/${agent.id}`} className="hover:underline focus-visible:outline-2 focus-visible:outline-ring">
              {agent.name}
            </Link>
          </h2>
          <p className="text-xs text-fg-muted">
            {CATEGORY_LABELS[agent.category]} · v{agent.version}
          </p>
        </div>
        <AgentActionsMenu agent={agent} onExecute={onExecute} onDelete={onDelete} />
      </div>
      <p className="mt-3 line-clamp-2 flex-1 text-sm text-fg-muted">{agent.description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <AgentStatusBadge status={agent.status} />
        <VerificationBadge status={agent.verification} />
        <RiskBadge level={agent.riskLevel} />
      </div>
      <p className="mt-3 border-t border-line pt-3 text-xs text-fg-subtle">
        By {agent.creator.name} · Updated {formatDate(agent.updatedAt)}
      </p>
    </article>
  );
}
