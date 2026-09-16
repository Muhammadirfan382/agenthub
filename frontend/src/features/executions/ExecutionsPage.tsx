import { Activity, SearchX } from 'lucide-react';
import { Link, useSearchParams } from 'react-router';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { PageHeader } from '@/components/layout/PageHeader';
import { ExecutionStatusBadge } from '@/components/status/StatusBadges';
import { EXECUTION_STATUS_META } from '@/components/status/meta';
import { Button } from '@/components/ui/Button';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { formatDateTime, formatDuration, formatNumber } from '@/lib/format';
import { EXECUTION_STATUSES, type Execution, type ExecutionStatus } from '@/types/domain';
import { useExecutions } from './api';
import { executionResultText, totalTokens } from './format';

const columns: Column<Execution>[] = [
  {
    id: 'id',
    header: 'Execution ID',
    primary: true,
    cell: (e) => (
      <Link to={`/executions/${e.id}`} className="font-mono text-xs font-medium text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
        {e.id}
      </Link>
    ),
  },
  { id: 'agent', header: 'Agent', cell: (e) => <span className="font-medium text-fg">{e.agentName}</span> },
  { id: 'status', header: 'Status', cell: (e) => <ExecutionStatusBadge status={e.status} /> },
  { id: 'started', header: 'Start time', cell: (e) => <span className="whitespace-nowrap text-fg-muted">{formatDateTime(e.startedAt)}</span> },
  { id: 'duration', header: 'Duration', cell: (e) => <span className="tabular-nums text-fg-muted">{formatDuration(e.durationMs)}</span> },
  { id: 'model', header: 'Model', cell: (e) => <span className="font-mono text-xs text-fg-muted">{e.model}</span> },
  { id: 'tokens', header: 'Tokens', align: 'right', cell: (e) => <span className="tabular-nums text-fg-muted">{formatNumber(totalTokens(e))}</span> },
  { id: 'tools', header: 'Tool calls', align: 'right', cell: (e) => <span className="tabular-nums text-fg-muted">{e.toolCallCount}</span> },
  { id: 'result', header: 'Result', className: 'max-w-56', cell: (e) => <span className="line-clamp-2 text-fg-muted">{executionResultText(e)}</span> },
];

export default function ExecutionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusParam = searchParams.get('status');
  const status: ExecutionStatus | 'all' = EXECUTION_STATUSES.includes(statusParam as ExecutionStatus) ? (statusParam as ExecutionStatus) : 'all';
  const search = searchParams.get('q') ?? '';
  const query = useExecutions({ status, search });

  const update = (patch: { status?: ExecutionStatus | 'all'; search?: string }) => {
    const next = { status, search, ...patch };
    const out = new URLSearchParams();
    if (next.status !== 'all') out.set('status', next.status);
    if (next.search) out.set('q', next.search);
    setSearchParams(out, { replace: true });
  };

  return (
    <>
      <PageHeader title="Executions" description="Monitor agent runs: status, duration, model usage, tool calls and outcomes." />

      <DataNotice
        resource="executions"
        className="mb-6"
        demo="Executions are demonstration data and are not updated in real time. Real execution monitoring arrives with the agent runtime."
        live="Executions are records stored by the backend. Nothing runs yet, so a requested execution stays queued until the agent runtime exists."
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem]">
        <SearchInput label="Search executions" placeholder="Search by execution ID or agent" value={search} onChange={(e) => update({ search: e.target.value })} />
        <Select aria-label="Filter by status" value={status} onChange={(e) => update({ status: e.target.value as ExecutionStatus | 'all' })}>
          <option value="all">All statuses</option>
          {EXECUTION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {EXECUTION_STATUS_META[s].label}
            </option>
          ))}
        </Select>
      </div>

      <QueryState
        query={query}
        loading={<LoadingState variant="table" label="Loading executions…" />}
        errorTitle="Executions could not be loaded"
        isEmpty={(rows) => rows.length === 0}
        empty={
          status !== 'all' || search ? (
            <EmptyState
              icon={SearchX}
              title="No executions match these filters"
              action={
                <Button variant="secondary" size="sm" onClick={() => update({ status: 'all', search: '' })}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState icon={Activity} title="No executions yet" description="Executions appear here once agents run." />
          )
        }
      >
        {(rows) => (
          <>
            <p aria-live="polite" className="mb-3 text-sm text-fg-muted">
              {rows.length} {rows.length === 1 ? 'execution' : 'executions'}
            </p>
            <DataTable caption="Agent executions" columns={columns} rows={rows} getRowKey={(e) => e.id} />
          </>
        )}
      </QueryState>
    </>
  );
}
