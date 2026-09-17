import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { RiskBadge } from '@/components/status/StatusBadges';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { formatDate } from '@/lib/format';
import type { Agent, AgentVersion, VersionStatus } from '@/types/domain';
import { useAgentVersions } from '../api';

const VERSION_STATUS: Record<VersionStatus, { label: string; tone: BadgeTone }> = {
  draft: { label: 'Draft', tone: 'info' },
  published: { label: 'Published', tone: 'success' },
  deprecated: { label: 'Deprecated', tone: 'warning' },
};

const columns: Column<AgentVersion>[] = [
  {
    id: 'version',
    header: 'Version',
    primary: true,
    cell: (version) => (
      <span className="font-mono text-sm font-medium text-fg">v{version.version}</span>
    ),
  },
  {
    id: 'published',
    header: 'Published',
    cell: (version) => (
      <span className="whitespace-nowrap text-fg-muted">
        {version.publishedAt ? formatDate(version.publishedAt) : 'Not published'}
      </span>
    ),
  },
  {
    id: 'status',
    header: 'Status',
    cell: (version) => (
      <Badge tone={VERSION_STATUS[version.status].tone}>
        {VERSION_STATUS[version.status].label}
      </Badge>
    ),
  },
  { id: 'risk', header: 'Risk', cell: (version) => <RiskBadge level={version.riskLevel} /> },
  {
    id: 'changelog',
    header: 'Changes',
    className: 'min-w-72',
    cell: (version) => (
      <ul className="list-disc space-y-0.5 pl-4 text-fg-muted">
        {version.changelog.map((entry) => (
          <li key={entry}>{entry}</li>
        ))}
      </ul>
    ),
  },
  {
    id: 'by',
    header: 'Published by',
    hideOnMobile: true,
    cell: (version) => <span className="text-fg-muted">{version.createdBy}</span>,
  },
];

/** History comes from publishing: each row is a frozen manifest. */
export function AgentVersionsTab({ agent }: { agent: Agent }) {
  const query = useAgentVersions(agent.id);

  return (
    <QueryState
      query={query}
      loading={<LoadingState variant="table" label="Loading versions…" />}
      errorTitle="Versions could not be loaded"
      isEmpty={(versions) => versions.length === 0}
      empty={
        <EmptyState
          title="Nothing published yet"
          description="Publishing freezes the current configuration as a version. Until then there is no history."
        />
      }
    >
      {(versions) => (
        <DataTable
          caption={`Published versions of ${agent.name}`}
          columns={columns}
          rows={versions}
          getRowKey={(version) => version.id}
        />
      )}
    </QueryState>
  );
}
