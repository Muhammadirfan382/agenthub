import { Link } from 'react-router';
import { AgentStatusBadge, RiskBadge, VerificationBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { formatDate, formatRelative } from '@/lib/format';
import type { AgentSort } from '@/services/contracts';
import type { Agent } from '@/types/domain';
import { AgentActionsMenu } from './AgentActionsMenu';

interface AgentTableProps {
  agents: Agent[];
  sort: AgentSort;
  onSortChange: (sort: AgentSort) => void;
  onExecute: (agent: Agent) => void;
  onDelete: (agent: Agent) => void;
}

export function AgentTable({ agents, sort, onSortChange, onExecute, onDelete }: AgentTableProps) {
  const sortFor = (key: AgentSort, direction: 'asc' | 'desc') => ({
    direction: sort === key ? direction : null,
    onToggle: () => onSortChange(key),
  });

  const columns: Column<Agent>[] = [
    {
      id: 'name',
      header: 'Agent',
      primary: true,
      sort: sortFor('name_asc', 'asc'),
      className: 'min-w-60',
      cell: (agent) => (
        <div className="min-w-0">
          <Link to={`/agents/${agent.id}`} className="font-medium text-fg hover:text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
            {agent.name}
          </Link>
          <p className="line-clamp-1 max-w-xs text-xs text-fg-muted">{agent.description}</p>
          <p className="mt-0.5 text-xs text-fg-subtle">{CATEGORY_LABELS[agent.category]}</p>
        </div>
      ),
    },
    { id: 'status', header: 'Status', cell: (agent) => <AgentStatusBadge status={agent.status} /> },
    { id: 'verification', header: 'Verification', cell: (agent) => <VerificationBadge status={agent.verification} /> },
    { id: 'risk', header: 'Risk', sort: sortFor('risk_desc', 'desc'), cell: (agent) => <RiskBadge level={agent.riskLevel} /> },
    { id: 'version', header: 'Version', cell: (agent) => <span className="font-mono text-xs text-fg-muted">v{agent.version}</span> },
    {
      id: 'owner',
      header: 'Creator / owner',
      cell: (agent) => (
        <span className="text-fg-muted">
          {agent.creator.name}
          {agent.owner.id !== agent.creator.id && <span className="block text-xs text-fg-subtle">Owner: {agent.owner.name}</span>}
        </span>
      ),
    },
    {
      id: 'lastExecution',
      header: 'Last execution',
      sort: sortFor('last_execution_desc', 'desc'),
      cell: (agent) => <span className="whitespace-nowrap text-fg-muted">{agent.lastExecutionAt ? formatRelative(agent.lastExecutionAt) : 'Never'}</span>,
    },
    { id: 'updated', header: 'Updated', sort: sortFor('updated_desc', 'desc'), cell: (agent) => <span className="whitespace-nowrap text-fg-muted">{formatDate(agent.updatedAt)}</span> },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      cell: (agent) => <AgentActionsMenu agent={agent} onExecute={onExecute} onDelete={onDelete} />,
    },
  ];

  return <DataTable caption="Agents" columns={columns} rows={agents} getRowKey={(agent) => agent.id} />;
}
