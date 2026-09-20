import { ScrollText } from 'lucide-react';
import { useState } from 'react';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { Alert } from '@/components/ui/Alert';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { type Column, DataTable } from '@/components/ui/DataTable';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { usePermission } from '@/features/auth/api';
import { formatDateTime } from '@/lib/format';
import type { AuditEvent, AuditQuery } from '@/types/domain';
import { useAuditEvents } from '../api';

const AREAS = [
  { value: '', label: 'Everything' },
  { value: 'policy.', label: 'Policy refusals' },
  { value: 'egress.', label: 'Outbound requests' },
  { value: 'auth.', label: 'Sign-ins and passwords' },
  { value: 'member.', label: 'Members and roles' },
  { value: 'runtime.', label: 'Kill switch' },
  { value: 'approval.', label: 'Approvals' },
  { value: 'agent.', label: 'Agents' },
  { value: 'installation.', label: 'Installations' },
] as const;

const OUTCOMES: { value: '' | AuditEvent['outcome']; label: string }[] = [
  { value: '', label: 'Any outcome' },
  { value: 'denied', label: 'Denied' },
  { value: 'failure', label: 'Failed' },
  { value: 'allowed', label: 'Allowed' },
  { value: 'success', label: 'Succeeded' },
];

const OUTCOME_TONE: Record<AuditEvent['outcome'], BadgeTone> = {
  success: 'success',
  allowed: 'info',
  failure: 'warning',
  denied: 'danger',
};

/** Detail is shown as compact text: it is data, never markup. */
function describe(detail: Record<string, unknown>): string {
  const entries = Object.entries(detail);
  if (entries.length === 0) return '—';
  return entries
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' · ');
}

const columns: Column<AuditEvent>[] = [
  {
    id: 'action',
    header: 'Action',
    primary: true,
    cell: (event) => <span className="font-mono text-xs font-medium text-fg">{event.action}</span>,
  },
  {
    id: 'outcome',
    header: 'Outcome',
    cell: (event) => <Badge tone={OUTCOME_TONE[event.outcome]}>{event.outcome}</Badge>,
  },
  {
    id: 'actor',
    header: 'By',
    cell: (event) => (
      <span className="text-fg">
        {event.actorName}
        <span className="ml-1 text-xs text-fg-subtle">({event.actorType})</span>
      </span>
    ),
  },
  {
    id: 'detail',
    header: 'Detail',
    className: 'max-w-72',
    cell: (event) => <span className="text-xs break-words text-fg-muted">{describe(event.detail)}</span>,
  },
  {
    id: 'at',
    header: 'When',
    cell: (event) => <span className="text-xs text-fg-muted">{formatDateTime(event.at)}</span>,
  },
];

/**
 * The organization's audit log: who did what, and what the platform decided.
 * Read-only - nothing in AgentHub edits or deletes an entry.
 */
export function AuditSettings() {
  const permitted = usePermission();
  const [area, setArea] = useState('');
  const [outcome, setOutcome] = useState<'' | AuditEvent['outcome']>('');
  const allowed = permitted('audit:read');

  const query: AuditQuery = {
    ...(area ? { action: area } : {}),
    ...(outcome ? { outcome } : {}),
  };
  const events = useAuditEvents(query, allowed);

  return (
    <div className="space-y-6">
      <DataNotice
        resource="audit"
        demo="Demo mode has no backend, so nothing is recorded and the log is empty."
        live="Recorded by the server as it happened. Entries cannot be edited or deleted."
      />
      <Card>
        <CardHeader
          title="Audit log"
          description="Sign-ins, role changes, the kill switch, approvals, policy refusals and every request an agent sent out."
        />
        <CardBody className="space-y-4">
          {!allowed ? (
            <Alert tone="info" title="Only administrators can read the audit log">
              Who did what is sensitive in itself. Ask an administrator or the owner.
            </Alert>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Area">
                  {(control) => (
                    <Select {...control} value={area} onChange={(event) => setArea(event.target.value)}>
                      {AREAS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="Outcome">
                  {(control) => (
                    <Select
                      {...control}
                      value={outcome}
                      onChange={(event) => setOutcome(event.target.value as '' | AuditEvent['outcome'])}
                    >
                      {OUTCOMES.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </div>
              <QueryState
                query={events}
                loading={<LoadingState variant="inline" label="Loading the audit log…" />}
                errorTitle="The audit log could not be loaded"
              >
                {(rows) =>
                  rows.length === 0 ? (
                    <EmptyState
                      icon={ScrollText}
                      title="Nothing recorded"
                      description="No event matches these filters."
                      className="py-8"
                    />
                  ) : (
                    <DataTable columns={columns} rows={rows} getRowKey={(event) => event.id} caption="Audit events" />
                  )
                }
              </QueryState>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
