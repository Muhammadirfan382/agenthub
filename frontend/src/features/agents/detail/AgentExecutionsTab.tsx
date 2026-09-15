import { Activity } from 'lucide-react';
import { Link } from 'react-router';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { ExecutionStatusBadge } from '@/components/status/StatusBadges';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { useExecutions } from '@/features/executions/api';
import { executionResultText, totalTokens } from '@/features/executions/format';
import { formatDuration, formatNumber, formatRelative } from '@/lib/format';
import type { Agent, Execution } from '@/types/domain';

const columns: Column<Execution>[] = [
  {
    id: 'id',
    header: 'Execution ID',
    primary: true,
    cell: (e) => (
      <Link to={`/executions/${e.id}`} className="font-mono text-xs text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
        {e.id}
      </Link>
    ),
  },
  { id: 'status', header: 'Status', cell: (e) => <ExecutionStatusBadge status={e.status} /> },
  { id: 'started', header: 'Started', cell: (e) => <span className="whitespace-nowrap text-fg-muted">{formatRelative(e.startedAt)}</span> },
  { id: 'duration', header: 'Duration', cell: (e) => <span className="tabular-nums text-fg-muted">{formatDuration(e.durationMs)}</span> },
  { id: 'tokens', header: 'Tokens', cell: (e) => <span className="tabular-nums text-fg-muted">{formatNumber(totalTokens(e))}</span> },
  { id: 'result', header: 'Result', className: 'max-w-64', cell: (e) => <span className="line-clamp-2 text-fg-muted">{executionResultText(e)}</span> },
];

export function AgentExecutionsTab({ agent }: { agent: Agent }) {
  const query = useExecutions({ agentId: agent.id });
  return (
    <QueryState
      query={query}
      loading={<LoadingState variant="table" label="Loading executions…" />}
      errorTitle="Executions could not be loaded"
      isEmpty={(rows) => rows.length === 0}
      empty={<EmptyState icon={Activity} title="No executions yet" description={`${agent.name} has not been executed.`} />}
    >
      {(rows) => <DataTable caption={`Recent executions of ${agent.name}`} columns={columns} rows={rows} getRowKey={(e) => e.id} />}
    </QueryState>
  );
}
