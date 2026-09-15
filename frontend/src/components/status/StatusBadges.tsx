import { cn } from '@/lib/cn';
import { Badge } from '@/components/ui/Badge';
import type {
  AgentStatus,
  ComponentState,
  ExecutionStatus,
  PolicyEnforcement,
  RiskLevel,
  SecurityCheckStatus,
  SecurityEventStatus,
  VerificationStatus,
} from '@/types/domain';
import {
  AGENT_STATUS_META,
  COMPONENT_STATE_META,
  EVENT_STATUS_META,
  EXECUTION_STATUS_META,
  POLICY_META,
  RISK_META,
  SECURITY_CHECK_META,
  VERIFICATION_META,
} from './meta';

/*
 * Every badge shows a text label next to its icon and colour, so status is
 * never communicated by colour or icon alone.
 */

const iconClass = 'size-3 shrink-0';

export function ExecutionStatusBadge({ status, className }: { status: ExecutionStatus; className?: string }) {
  const meta = EXECUTION_STATUS_META[status];
  const Icon = meta.icon;
  const animate = status === 'STARTING' ? 'animate-spin' : status === 'RUNNING' ? 'animate-pulse-dot' : '';
  return (
    <Badge tone={meta.tone} className={className} icon={<Icon aria-hidden="true" className={cn(iconClass, animate)} />}>
      {meta.label}
    </Badge>
  );
}

export function RiskBadge({ level, className, suffix = true }: { level: RiskLevel; className?: string; suffix?: boolean }) {
  const meta = RISK_META[level];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {suffix ? `${meta.label} risk` : meta.label}
    </Badge>
  );
}

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const meta = AGENT_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {meta.label}
    </Badge>
  );
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const meta = VERIFICATION_META[status];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {meta.label}
    </Badge>
  );
}

export function ComponentStateBadge({ state }: { state: ComponentState }) {
  const meta = COMPONENT_STATE_META[state];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {meta.label}
    </Badge>
  );
}

export function SecurityCheckBadge({ status }: { status: SecurityCheckStatus }) {
  const meta = SECURITY_CHECK_META[status];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {meta.label}
    </Badge>
  );
}

export function EventStatusBadge({ status }: { status: SecurityEventStatus }) {
  const meta = EVENT_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {meta.label}
    </Badge>
  );
}

export function PolicyBadge({ enforcement }: { enforcement: PolicyEnforcement }) {
  const meta = POLICY_META[enforcement];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon aria-hidden="true" className={iconClass} />}>
      {meta.label}
    </Badge>
  );
}
