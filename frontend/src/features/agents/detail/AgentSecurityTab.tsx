import { DemoNotice } from '@/components/feedback/DemoNotice';
import { RiskBadge, SecurityCheckBadge, VerificationBadge } from '@/components/status/StatusBadges';
import { RISK_META } from '@/components/status/meta';
import { Badge } from '@/components/ui/Badge';
import { Card, CardHeader } from '@/components/ui/Card';
import { Meter, type MeterTone } from '@/components/ui/Meter';
import type { Agent, RiskLevel } from '@/types/domain';

const METER_TONE: Record<RiskLevel, MeterTone> = { low: 'success', medium: 'warning', high: 'high', critical: 'danger' };

export function AgentSecurityTab({ agent }: { agent: Agent }) {
  const policy = agent.securityPolicy;
  return (
    <div className="space-y-6">
      <DemoNotice title="Demo security data">
        Risk scores, verification and check results are illustrative. Real security scanning is not implemented yet.
      </DemoNotice>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Risk score" />
          <div className="space-y-3 px-5 py-4">
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-semibold text-fg tabular-nums">{agent.riskScore}</span>
              <RiskBadge level={agent.riskLevel} />
            </div>
            <Meter
              value={agent.riskScore}
              label="Risk score"
              valueText={`${agent.riskScore} out of 100, ${RISK_META[agent.riskLevel].label.toLowerCase()} risk`}
              tone={METER_TONE[agent.riskLevel]}
            />
            <p className="text-xs text-fg-subtle">0 is lowest risk, 100 is highest.</p>
          </div>
        </Card>

        <Card>
          <CardHeader title="Verification" />
          <div className="space-y-2 px-5 py-4">
            <VerificationBadge status={agent.verification} />
            <p className="text-sm text-fg-muted">
              {agent.verification === 'verified'
                ? 'Passed the demo review process.'
                : agent.verification === 'pending'
                  ? 'Awaiting review before it can be marked verified.'
                  : agent.verification === 'rejected'
                    ? 'Failed review. Resolve the findings before resubmitting.'
                    : 'Not submitted for verification.'}
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader title="Security policy" />
          <dl className="space-y-2 px-5 py-4 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-fg-muted">Sandbox</dt>
              <dd className="font-medium text-fg capitalize">{policy.sandbox}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-fg-muted">Network egress</dt>
              <dd className="font-medium text-fg">{policy.networkEgress === 'none' ? 'None' : 'Allow-list'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-fg-muted">Approval required for</dt>
              <dd className="flex flex-wrap justify-end gap-1">
                {policy.approvalRequiredFor.length === 0 ? 'Nothing' : policy.approvalRequiredFor.map((level) => <Badge key={level}>{RISK_META[level].label}</Badge>)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-fg-muted">Audit logging</dt>
              <dd className="font-medium text-fg">{policy.auditLogging ? 'On' : 'Off'}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <Card>
        <CardHeader title="Security checks" description="Illustrative results; no scanner has run." />
        <ul className="divide-y divide-line">
          {agent.securityChecks.map((check) => (
            <li key={check.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg">{check.name}</p>
                <p className="text-xs text-fg-muted">{check.detail}</p>
              </div>
              <SecurityCheckBadge status={check.status} />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
