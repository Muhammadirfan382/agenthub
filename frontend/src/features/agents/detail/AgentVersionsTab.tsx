import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { formatDate } from '@/lib/format';
import type { Agent, AgentVersion, VersionStatus } from '@/types/domain';

const VERSION_STATUS: Record<VersionStatus, { label: string; tone: BadgeTone }> = {
  current: { label: 'Current', tone: 'success' },
  previous: { label: 'Previous', tone: 'neutral' },
  deprecated: { label: 'Deprecated', tone: 'warning' },
  draft: { label: 'Draft', tone: 'info' },
};

const columns: Column<AgentVersion>[] = [
  { id: 'version', header: 'Version', primary: true, cell: (v) => <span className="font-mono text-sm font-medium text-fg">v{v.version}</span> },
  { id: 'released', header: 'Release date', cell: (v) => <span className="whitespace-nowrap text-fg-muted">{formatDate(v.releasedAt)}</span> },
  { id: 'status', header: 'Status', cell: (v) => <Badge tone={VERSION_STATUS[v.status].tone}>{VERSION_STATUS[v.status].label}</Badge> },
  {
    id: 'changes',
    header: 'Changes',
    className: 'min-w-72',
    cell: (v) => (
      <ul className="list-disc space-y-0.5 pl-4 text-fg-muted">
        {v.changes.map((change) => (
          <li key={change}>{change}</li>
        ))}
      </ul>
    ),
  },
];

export function AgentVersionsTab({ agent }: { agent: Agent }) {
  return <DataTable caption={`Version history for ${agent.name}`} columns={columns} rows={agent.versions} getRowKey={(v) => v.version} />;
}
