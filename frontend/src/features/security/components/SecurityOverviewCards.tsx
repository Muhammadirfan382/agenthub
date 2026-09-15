import { SecurityCheckBadge } from '@/components/status/StatusBadges';
import { RISK_META } from '@/components/status/meta';
import { Card, CardHeader } from '@/components/ui/Card';
import { Meter, type MeterTone } from '@/components/ui/Meter';
import type { RiskLevel, SecurityCheckStatus, SecurityOverview } from '@/types/domain';
import { RISK_LEVELS } from '@/types/domain';

const RISK_TONE: Record<RiskLevel, MeterTone> = { low: 'success', medium: 'warning', high: 'high', critical: 'danger' };
const CHECK_ORDER: SecurityCheckStatus[] = ['passed', 'warning', 'failed', 'not_run'];

export function RiskDistributionCard({ overview }: { overview: SecurityOverview }) {
  const total = Math.max(1, RISK_LEVELS.reduce((sum, level) => sum + overview.riskDistribution[level], 0));
  return (
    <Card>
      <CardHeader title="Agent risk levels" description="Number of agents in each risk classification." />
      <ul className="space-y-4 px-5 py-4">
        {RISK_LEVELS.map((level) => {
          const count = overview.riskDistribution[level];
          const Icon = RISK_META[level].icon;
          return (
            <li key={level}>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="inline-flex items-center gap-1.5 font-medium text-fg">
                  <Icon aria-hidden="true" className="size-4 text-fg-muted" />
                  {RISK_META[level].label}
                </span>
                <span className="text-fg-muted tabular-nums">
                  {count} {count === 1 ? 'agent' : 'agents'}
                </span>
              </div>
              <Meter value={count} max={total} label={`${RISK_META[level].label} risk agents`} valueText={`${count} of ${total} agents`} tone={RISK_TONE[level]} />
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export function SecurityChecksCard({ overview }: { overview: SecurityOverview }) {
  return (
    <Card>
      <CardHeader title="Security checks" description="Results across all agents (illustrative)." />
      <ul className="divide-y divide-line px-5">
        {CHECK_ORDER.map((status) => (
          <li key={status} className="flex items-center justify-between py-3">
            <SecurityCheckBadge status={status} />
            <span className="text-sm font-medium text-fg tabular-nums">{overview.checks[status]}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
