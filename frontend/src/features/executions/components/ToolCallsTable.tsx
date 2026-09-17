import { Wrench } from 'lucide-react';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { formatDuration, formatTime } from '@/lib/format';
import type { ToolCall, ToolCallStatus } from '@/types/domain';

const STATUS: Record<ToolCallStatus, { label: string; tone: BadgeTone }> = {
  // Nothing was executed: the runtime recorded the request instead.
  simulated: { label: 'Simulated', tone: 'info' },
  failed: { label: 'Failed', tone: 'danger' },
  denied: { label: 'Denied by policy', tone: 'high' },
  pending: { label: 'Pending', tone: 'warning' },
};

const columns: Column<ToolCall>[] = [
  { id: 'tool', header: 'Tool', primary: true, cell: (t) => <span className="font-mono text-xs font-medium text-fg">{t.tool}</span> },
  { id: 'status', header: 'Status', cell: (t) => <Badge tone={STATUS[t.status].tone}>{STATUS[t.status].label}</Badge> },
  { id: 'started', header: 'Started', cell: (t) => <span className="font-mono text-xs text-fg-muted">{formatTime(t.startedAt)}</span> },
  { id: 'duration', header: 'Duration', cell: (t) => <span className="tabular-nums text-fg-muted">{formatDuration(t.durationMs)}</span> },
  { id: 'input', header: 'Input', className: 'max-w-64', cell: (t) => <span className="text-fg-muted">{t.inputSummary}</span> },
  { id: 'output', header: 'Output', className: 'max-w-64', cell: (t) => <span className="text-fg-muted">{t.outputSummary ?? '—'}</span> },
];

export function ToolCallsTable({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (toolCalls.length === 0) {
    return <EmptyState icon={Wrench} title="No tool calls" description="The agent has not called any tools in this execution." />;
  }
  return <DataTable caption="Tool calls" columns={columns} rows={toolCalls} getRowKey={(t) => t.id} />;
}
