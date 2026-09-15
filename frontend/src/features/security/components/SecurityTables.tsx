import { ShieldCheck } from 'lucide-react';
import { Link } from 'react-router';
import { EmptyState } from '@/components/feedback/EmptyState';
import { EventStatusBadge, PolicyBadge, RiskBadge } from '@/components/status/StatusBadges';
import { CAPABILITY_META } from '@/components/status/meta';
import { Alert } from '@/components/ui/Alert';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { formatRelative } from '@/lib/format';
import type { PermissionOverviewRow, PlatformPolicy, SecurityEvent } from '@/types/domain';

const permissionColumns: Column<PermissionOverviewRow>[] = [
  { id: 'capability', header: 'Capability', primary: true, cell: (r) => <span className="font-medium text-fg">{CAPABILITY_META[r.capability].label}</span> },
  { id: 'allowed', header: 'Allowed', align: 'right', cell: (r) => <span className="tabular-nums">{r.allowed}</span> },
  { id: 'restricted', header: 'Restricted / read only', align: 'right', cell: (r) => <span className="tabular-nums">{r.restricted}</span> },
  { id: 'approval', header: 'Requires approval', align: 'right', cell: (r) => <span className="tabular-nums">{r.requiresApproval}</span> },
  { id: 'denied', header: 'Denied', align: 'right', cell: (r) => <span className="tabular-nums text-fg-muted">{r.denied}</span> },
];

export function PermissionOverviewTable({ rows }: { rows: PermissionOverviewRow[] }) {
  return <DataTable caption="Permission overview: agents per access level" columns={permissionColumns} rows={rows} getRowKey={(r) => r.capability} />;
}

const eventColumns: Column<SecurityEvent>[] = [
  { id: 'severity', header: 'Severity', cell: (e) => <RiskBadge level={e.severity} suffix={false} /> },
  {
    id: 'type',
    header: 'Event',
    primary: true,
    className: 'min-w-64',
    cell: (e) => (
      <div>
        <p className="font-medium text-fg">{e.type}</p>
        <p className="text-xs text-fg-muted">{e.description}</p>
      </div>
    ),
  },
  {
    id: 'agent',
    header: 'Agent',
    cell: (e) =>
      e.agentId ? (
        <Link to={`/agents/${e.agentId}`} className="text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring">
          {e.agentName}
        </Link>
      ) : (
        e.agentName
      ),
  },
  { id: 'detected', header: 'Detected', cell: (e) => <span className="whitespace-nowrap text-fg-muted">{formatRelative(e.detectedAt)}</span> },
  { id: 'status', header: 'Status', cell: (e) => <EventStatusBadge status={e.status} /> },
];

export function SecurityEventsTable({ events }: { events: SecurityEvent[] }) {
  if (events.length === 0) return <EmptyState icon={ShieldCheck} title="No security events" />;
  return <DataTable caption="Recent security events" columns={eventColumns} rows={events} getRowKey={(e) => e.id} />;
}

export function AlertsList({ events }: { events: SecurityEvent[] }) {
  const alerts = events.filter((e) => e.status !== 'resolved' && (e.severity === 'critical' || e.severity === 'high'));
  if (alerts.length === 0) {
    return <Alert tone="success" title="No open high or critical alerts" />;
  }
  return (
    <ul className="space-y-3">
      {alerts.map((event) => (
        <li key={event.id}>
          <Alert tone={event.severity === 'critical' ? 'danger' : 'warning'} title={`${event.severity === 'critical' ? 'Critical' : 'High'}: ${event.type}`}>
            {event.agentName} · {event.description} · {formatRelative(event.detectedAt)}
          </Alert>
        </li>
      ))}
    </ul>
  );
}

export function PolicyList({ policies }: { policies: PlatformPolicy[] }) {
  return (
    <ul className="divide-y divide-line">
      {policies.map((policy) => (
        <li key={policy.id} className="flex flex-wrap items-start justify-between gap-3 px-5 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-fg">{policy.name}</p>
            <p className="text-xs text-fg-muted">{policy.description}</p>
          </div>
          <PolicyBadge enforcement={policy.enforcement} />
        </li>
      ))}
    </ul>
  );
}
