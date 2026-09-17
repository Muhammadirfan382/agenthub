import { Ban, SearchX } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { Link, useParams } from 'react-router';
import { DataNotice, DemoBadge } from '@/components/feedback/DemoNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { PageHeader } from '@/components/layout/PageHeader';
import { ExecutionStatusBadge } from '@/components/status/StatusBadges';
import { Alert } from '@/components/ui/Alert';
import { Button, LinkButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Badge } from '@/components/ui/Badge';

import { Card, CardHeader } from '@/components/ui/Card';
import { formatDateTime, formatDuration, formatNumber } from '@/lib/format';
import { type ExecutionDetail, isExecutionFinished } from '@/types/domain';
import { usePermission } from '@/features/auth/api';
import { useIsLive } from '@/services/useIsLive';
import { toast } from '@/stores/toastStore';
import { useCancelExecution, useExecution, useExecutionStream } from './api';

/** An empty trace means different things in demo mode and against the real backend. */
function ExecutionTraceBadge() {
  const live = useIsLive('executions');
  return live ? <Badge tone="neutral">No trace recorded</Badge> : <DemoBadge label="Demo data · not real-time" />;
}
import { ApprovalPanel } from './components/ApprovalPanel';
import { ExecutionTimeline } from './components/ExecutionTimeline';
import { LogList } from './components/LogList';
import { ToolCallsTable } from './components/ToolCallsTable';

export default function ExecutionDetailPage() {
  const { id = '' } = useParams();
  const query = useExecution(id);
  const live = Boolean(query.data && !isExecutionFinished(query.data.status));
  // Watch the server's stream while the run is live; polling covers the rest.
  useExecutionStream(id, live);

  if (query.isPending) return <LoadingState label="Loading execution…" />;
  if (query.isError) return <ErrorState title="Execution could not be loaded" onRetry={() => void query.refetch()} retrying={query.isFetching} />;
  if (!query.data) {
    return (
      <EmptyState
        icon={SearchX}
        title="Execution not found"
        description="This execution does not exist."
        action={
          <LinkButton to="/executions" variant="primary" size="sm">
            Back to executions
          </LinkButton>
        }
      />
    );
  }
  return <Detail execution={query.data} />;
}

function Detail({ execution }: { execution: ExecutionDetail }) {
  const permitted = usePermission();
  const cancel = useCancelExecution();
  const [confirmCancel, setConfirmCancel] = useState(false);
  const finished = isExecutionFinished(execution.status);

  const metadata: [string, ReactNode][] = [
    [
      'Agent',
      <Link key="agent" to={`/agents/${execution.agentId}`} className="text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
        {execution.agentName}
      </Link>,
    ],
    ['Status', <ExecutionStatusBadge key="status" status={execution.status} />],
    ['Trigger', <span key="trigger" className="capitalize">{execution.trigger}</span>],
    ['Model', <span key="model" className="font-mono text-xs">{execution.model}</span>],
    ['Started', formatDateTime(execution.startedAt)],
    ['Ended', execution.endedAt ? formatDateTime(execution.endedAt) : 'Not finished'],
    ['Duration', formatDuration(execution.durationMs)],
    ['Tool calls', formatNumber(execution.toolCallCount)],
    ['Input tokens', formatNumber(execution.tokenUsage.input)],
    ['Output tokens', formatNumber(execution.tokenUsage.output)],
    ['Requested by', execution.requestedBy || 'Unknown'],
    [
      'Budget',
      `${execution.budget.maxRuntimeSeconds}s · ${formatNumber(execution.budget.maxTokens)} tokens · ${execution.budget.maxToolCalls} tool calls`,
    ],
  ];

  return (
    <>
      <PageHeader
        title={execution.id}
        documentTitle={`Execution ${execution.id}`}
        description={`Execution of ${execution.agentName}.`}
        breadcrumbs={[{ label: 'Executions', to: '/executions' }, { label: execution.id }]}
        meta={
          <>
            <ExecutionStatusBadge status={execution.status} />
            <ExecutionTraceBadge />
            {execution.cancelRequested && !finished && <Badge tone="warning">Stopping</Badge>}
          </>
        }
        actions={
          finished ? null : (
            <Button
              variant="secondary"
              onClick={() => setConfirmCancel(true)}
              disabled={!permitted('agent:execute') || execution.cancelRequested}
            >
              <Ban aria-hidden="true" className="size-4" />
              {execution.cancelRequested ? 'Stopping…' : 'Cancel run'}
            </Button>
          )
        }
      />

      <DataNotice
        resource="executions"
        className="mb-6"
        demo="Timeline, logs and tool calls are generated demonstration data. They are not streamed from a running agent."
        live="The runtime orchestrated this run and recorded every step, but executed nothing: there is no sandbox yet, so no agent code, model or tool was actually run."
      />

      {execution.error && (
        <Alert tone="danger" title={`Error: ${execution.error.code}`} className="mb-6">
          {execution.error.message}
        </Alert>
      )}

      {execution.approvals.length > 0 && (
        <div className="mb-6">
          <ApprovalPanel approvals={execution.approvals} />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-1">
          <CardHeader title="Metadata" />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-5 py-4">
            {metadata.map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-xs text-fg-subtle">{label}</dt>
                <dd className="mt-0.5 text-sm text-fg">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader title="Result" />
            <div className="px-5 py-4 text-sm">
              {execution.result ? (
                <p className="text-fg">{execution.result}</p>
              ) : (
                <p className="text-fg-muted">
                  {execution.status === 'COMPLETED' ? 'No result was recorded.' : 'No result: the execution has not completed successfully.'}
                </p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Timeline" />
            <div className="px-5 py-4">
              <ExecutionTimeline events={execution.timeline} />
            </div>
          </Card>
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader title="Tool calls" description="Every tool the agent requested during this execution." />
        <div className="p-4">
          <ToolCallsTable toolCalls={execution.toolCalls} />
        </div>
      </Card>

      <Card className="mt-6">
        <CardHeader
          title="Logs"
          description="What the runtime wrote while orchestrating this run."
        />
        <div className="p-4">
          <LogList logs={execution.logs} />
        </div>
      </Card>

      <ConfirmDialog
        open={confirmCancel}
        tone="danger"
        title="Cancel this run?"
        description="The runtime stops it at the next step boundary. Steps already recorded stay in the record."
        confirmLabel="Stop the run"
        pending={cancel.isPending}
        onCancel={() => setConfirmCancel(false)}
        onConfirm={() =>
          cancel.mutate(execution.id, {
            onSuccess: () => {
              setConfirmCancel(false);
              toast.success('Cancellation requested', 'The run stops at the next step.');
            },
            onError: (error) => {
              setConfirmCancel(false);
              toast.danger('Could not cancel', error.message);
            },
          })
        }
      />
    </>
  );
}
