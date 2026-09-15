import { Link } from 'react-router';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { ExecutionStatusBadge } from '@/components/status/StatusBadges';
import { Card, CardHeader } from '@/components/ui/Card';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { useExecutions } from '@/features/executions/api';
import { executionResultText } from '@/features/executions/format';
import { formatDuration, formatRelative } from '@/lib/format';
import type { Execution } from '@/types/domain';

const columns: Column<Execution>[] = [
  { id: 'agent', header: 'Agent', primary: true, cell: (e) => <span className="font-medium text-fg">{e.agentName}</span> },
  {
    id: 'id',
    header: 'Execution ID',
    cell: (e) => (
      <Link to={`/executions/${e.id}`} className="font-mono text-xs text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
        {e.id}
      </Link>
    ),
  },
  { id: 'status', header: 'Status', cell: (e) => <ExecutionStatusBadge status={e.status} /> },
  { id: 'started', header: 'Started', cell: (e) => <span className="whitespace-nowrap text-fg-muted">{formatRelative(e.startedAt)}</span> },
  { id: 'duration', header: 'Duration', cell: (e) => <span className="tabular-nums text-fg-muted">{formatDuration(e.durationMs)}</span> },
  { id: 'result', header: 'Result', className: 'max-w-64', cell: (e) => <span className="line-clamp-2 text-fg-muted">{executionResultText(e)}</span> },
];

export function RecentActivity() {
  const query = useExecutions();
  return (
    <Card>
      <CardHeader
        title="Recent activity"
        description="Latest agent executions (demo)."
        action={
          <Link to="/executions" className="text-sm font-medium text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
            View all
          </Link>
        }
      />
      <div className="p-4">
        <QueryState
          query={query}
          loading={<LoadingState variant="table" label="Loading recent activity…" />}
          errorTitle="Activity unavailable"
          isEmpty={(rows) => rows.length === 0}
          empty={<EmptyState title="No executions yet" description="Executions appear here once an agent runs." />}
        >
          {(rows) => <DataTable caption="Recent executions" columns={columns} rows={rows.slice(0, 6)} getRowKey={(e) => e.id} />}
        </QueryState>
      </div>
    </Card>
  );
}
