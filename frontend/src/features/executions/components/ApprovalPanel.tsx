import { Check, X } from 'lucide-react';
import { useState } from 'react';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CAPABILITY_META } from '@/components/status/meta';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { usePermission } from '@/features/auth/api';
import { formatDateTime } from '@/lib/format';
import { toast } from '@/stores/toastStore';
import type { Approval, CapabilityKey } from '@/types/domain';
import { useDecideApproval } from '../api';

function capabilityLabel(capability: string): string {
  return CAPABILITY_META[capability as CapabilityKey]?.label ?? capability;
}

/**
 * A paused step waits here until a person decides. Refusing is not a failure:
 * the run continues without that step, and the refusal is recorded.
 */
export function ApprovalPanel({ approvals }: { approvals: Approval[] }) {
  const permitted = usePermission();
  const canDecide = permitted('agent:execute');
  const decide = useDecideApproval();
  const [notes, setNotes] = useState<Record<string, string>>({});

  if (approvals.length === 0) return null;
  const pending = approvals.filter((approval) => approval.status === 'pending');

  const submit = (approval: Approval, decision: 'approved' | 'denied') =>
    decide.mutate(
      {
        executionId: approval.executionId,
        approvalId: approval.id,
        decision,
        note: notes[approval.id]?.trim() || undefined,
      },
      {
        onSuccess: () =>
          toast.success(
            decision === 'approved' ? 'Approved' : 'Refused',
            decision === 'approved'
              ? 'The run continues from where it paused.'
              : 'The step was refused and recorded.',
          ),
        onError: (error) => toast.danger('Decision not recorded', error.message),
      },
    );

  return (
    <Card>
      <CardHeader
        title="Approvals"
        description="Steps this agent may not take without a person agreeing."
      />
      <CardBody className="space-y-4">
        {pending.length > 0 && !canDecide && (
          <Alert tone="info" title="Your role cannot decide these">
            Ask an administrator, or the owner of this agent.
          </Alert>
        )}

        {approvals.map((approval) => (
          <div key={approval.id} className="rounded-lg border border-line p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg">
                  {approval.tool ? `${approval.tool} · ` : ''}
                  {capabilityLabel(approval.capability)}
                </p>
                <p className="mt-0.5 text-xs text-fg-muted">{approval.reason}</p>
                <p className="mt-1 text-xs text-fg-subtle">
                  Requested {formatDateTime(approval.requestedAt)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <RiskBadge level={approval.riskLevel} />
                {approval.status !== 'pending' && (
                  <Badge tone={approval.status === 'approved' ? 'success' : 'high'}>
                    {approval.status === 'approved' ? 'Approved' : 'Refused'}
                  </Badge>
                )}
              </div>
            </div>

            {approval.status === 'pending' ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
                <Input
                  aria-label={`Note for ${approval.tool ?? approval.capability}`}
                  placeholder="Note (optional): why you decided this"
                  value={notes[approval.id] ?? ''}
                  disabled={!canDecide || decide.isPending}
                  onChange={(event) =>
                    setNotes((current) => ({ ...current, [approval.id]: event.target.value }))
                  }
                />
                <Button
                  variant="secondary"
                  disabled={!canDecide || decide.isPending}
                  onClick={() => submit(approval, 'denied')}
                >
                  <X aria-hidden="true" className="size-4" />
                  Refuse
                </Button>
                <Button
                  variant="primary"
                  disabled={!canDecide || decide.isPending}
                  onClick={() => submit(approval, 'approved')}
                >
                  <Check aria-hidden="true" className="size-4" />
                  Approve
                </Button>
              </div>
            ) : (
              <p className="mt-2 text-xs text-fg-muted">
                {approval.status === 'approved' ? 'Approved' : 'Refused'} by{' '}
                {approval.decidedBy ?? 'an approver'}
                {approval.decidedAt ? ` on ${formatDateTime(approval.decidedAt)}` : ''}
                {approval.note ? ` — “${approval.note}”` : ''}
              </p>
            )}
          </div>
        ))}
      </CardBody>
    </Card>
  );
}
