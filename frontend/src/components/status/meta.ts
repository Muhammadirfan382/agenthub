import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  Ban,
  BadgeCheck,
  CircleCheck,
  CircleDashed,
  CircleX,
  Clock,
  Code,
  Database,
  FileText,
  Globe,
  Hourglass,
  LoaderCircle,
  Mail,
  Plug,
  Shield,
  ShieldAlert,
  ShieldQuestionMark,
  ShieldCheck,
  ShieldX,
  TimerOff,
  TriangleAlert,
  Wrench,
} from 'lucide-react';
import type { BadgeTone } from '@/components/ui/Badge';
import type {
  AgentCategory,
  AgentStatus,
  CapabilityKey,
  ComponentState,
  ExecutionStatus,
  PermissionLevel,
  PolicyEnforcement,
  RiskLevel,
  SecurityCheckStatus,
  SecurityEventStatus,
  VerificationStatus,
} from '@/types/domain';

interface Meta {
  label: string;
  tone: BadgeTone;
  icon: LucideIcon;
}

export const EXECUTION_STATUS_META: Record<ExecutionStatus, Meta> = {
  QUEUED: { label: 'Queued', tone: 'neutral', icon: Clock },
  STARTING: { label: 'Starting', tone: 'info', icon: LoaderCircle },
  RUNNING: { label: 'Running', tone: 'brand', icon: Activity },
  WAITING_FOR_TOOL: { label: 'Waiting for tool', tone: 'warning', icon: Wrench },
  WAITING_FOR_APPROVAL: { label: 'Waiting for approval', tone: 'warning', icon: ShieldQuestionMark },
  COMPLETED: { label: 'Completed', tone: 'success', icon: CircleCheck },
  FAILED: { label: 'Failed', tone: 'danger', icon: CircleX },
  CANCELLED: { label: 'Cancelled', tone: 'neutral', icon: Ban },
  TIMEOUT: { label: 'Timed out', tone: 'high', icon: TimerOff },
};

export const RISK_META: Record<RiskLevel, Meta> = {
  low: { label: 'Low', tone: 'success', icon: ShieldCheck },
  medium: { label: 'Medium', tone: 'warning', icon: Shield },
  high: { label: 'High', tone: 'high', icon: ShieldAlert },
  critical: { label: 'Critical', tone: 'danger', icon: ShieldX },
};

export const AGENT_STATUS_META: Record<AgentStatus, Meta> = {
  active: { label: 'Active', tone: 'success', icon: CircleCheck },
  paused: { label: 'Paused', tone: 'warning', icon: Hourglass },
  draft: { label: 'Draft', tone: 'neutral', icon: CircleDashed },
  disabled: { label: 'Disabled', tone: 'danger', icon: Ban },
};

export const VERIFICATION_META: Record<VerificationStatus, Meta> = {
  verified: { label: 'Verified', tone: 'success', icon: BadgeCheck },
  pending: { label: 'Verification pending', tone: 'info', icon: Hourglass },
  unverified: { label: 'Unverified', tone: 'neutral', icon: CircleDashed },
  rejected: { label: 'Rejected', tone: 'danger', icon: CircleX },
};

export const PERMISSION_LEVEL_META: Record<PermissionLevel, Meta> = {
  allowed: { label: 'Allowed', tone: 'success', icon: CircleCheck },
  restricted: { label: 'Restricted', tone: 'warning', icon: Shield },
  read_only: { label: 'Read only', tone: 'info', icon: FileText },
  denied: { label: 'Denied', tone: 'neutral', icon: Ban },
};

export const COMPONENT_STATE_META: Record<ComponentState, Meta> = {
  operational: { label: 'Operational', tone: 'success', icon: CircleCheck },
  degraded: { label: 'Degraded', tone: 'warning', icon: TriangleAlert },
  outage: { label: 'Outage', tone: 'danger', icon: CircleX },
};

export const SECURITY_CHECK_META: Record<SecurityCheckStatus, Meta> = {
  passed: { label: 'Passed', tone: 'success', icon: CircleCheck },
  warning: { label: 'Warning', tone: 'warning', icon: TriangleAlert },
  failed: { label: 'Failed', tone: 'danger', icon: CircleX },
  not_run: { label: 'Not run', tone: 'neutral', icon: CircleDashed },
};

export const EVENT_STATUS_META: Record<SecurityEventStatus, Meta> = {
  open: { label: 'Open', tone: 'danger', icon: CircleX },
  investigating: { label: 'Investigating', tone: 'warning', icon: Hourglass },
  resolved: { label: 'Resolved', tone: 'success', icon: CircleCheck },
};

export const POLICY_META: Record<PolicyEnforcement, Meta> = {
  enforced: { label: 'Enforced', tone: 'success', icon: ShieldCheck },
  monitoring: { label: 'Monitoring', tone: 'info', icon: Activity },
  disabled: { label: 'Disabled', tone: 'neutral', icon: Ban },
};

export const CAPABILITY_META: Record<CapabilityKey, { label: string; description: string; icon: LucideIcon }> = {
  web_access: { label: 'Web access', description: 'Fetch pages from the internet.', icon: Globe },
  api_access: { label: 'API access', description: 'Call external or internal APIs.', icon: Plug },
  file_access: { label: 'File access', description: 'Read or write files.', icon: FileText },
  database_access: { label: 'Database access', description: 'Query or modify databases.', icon: Database },
  tool_calling: { label: 'Tool calling', description: 'Invoke declared tools.', icon: Wrench },
  code_execution: { label: 'Code execution', description: 'Run code inside a sandbox.', icon: Code },
  email_send: { label: 'Send email', description: 'Send messages on your behalf.', icon: Mail },
};

export const CAPABILITY_KEYS = Object.keys(CAPABILITY_META) as CapabilityKey[];

export const CATEGORY_LABELS: Record<AgentCategory, string> = {
  research: 'Research',
  security: 'Security',
  engineering: 'Engineering',
  data: 'Data & analytics',
  operations: 'Operations',
  support: 'Customer support',
  marketing: 'Marketing',
};
