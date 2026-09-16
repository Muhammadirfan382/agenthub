/**
 * AgentHub API models.
 *
 * These types are the contract between the UI and the service layer. Demo
 * services return them today; the real backend (Phase 2+) must return the same
 * shapes, validated at the boundary.
 */

export type ID = string;
/** ISO-8601 timestamp. */
export type ISODate = string;

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export const RISK_LEVELS: readonly RiskLevel[] = ['low', 'medium', 'high', 'critical'];

export type AgentStatus = 'active' | 'paused' | 'draft' | 'disabled';
export type VerificationStatus = 'verified' | 'pending' | 'unverified' | 'rejected';

export type AgentCategory = 'research' | 'security' | 'engineering' | 'data' | 'operations' | 'support' | 'marketing';
export const AGENT_CATEGORIES: readonly AgentCategory[] = [
  'research',
  'security',
  'engineering',
  'data',
  'operations',
  'support',
  'marketing',
];

export type CapabilityKey =
  | 'web_access'
  | 'api_access'
  | 'file_access'
  | 'database_access'
  | 'tool_calling'
  | 'code_execution'
  | 'email_send';

/** How a capability is granted to an agent. Enforcement is a backend concern. */
export type PermissionLevel = 'denied' | 'read_only' | 'restricted' | 'allowed';

export interface AgentPermission {
  capability: CapabilityKey;
  level: PermissionLevel;
  requiresApproval: boolean;
  scope: string;
  risk: RiskLevel;
}

export type VersionStatus = 'current' | 'previous' | 'deprecated' | 'draft';

export interface AgentVersion {
  version: string;
  releasedAt: ISODate;
  status: VersionStatus;
  changes: string[];
}

export type SecurityCheckStatus = 'passed' | 'warning' | 'failed' | 'not_run';

export interface SecurityCheck {
  id: ID;
  name: string;
  status: SecurityCheckStatus;
  detail: string;
}

export interface ModelConfig {
  provider: string;
  model: string;
  temperature: number;
  maxOutputTokens: number;
}

export interface ResourceLimits {
  maxRuntimeSeconds: number;
  maxMemoryMb: number;
  maxTokensPerRun: number;
  maxToolCalls: number;
}

export type SandboxMode = 'strict' | 'standard';

export interface SecurityPolicy {
  sandbox: SandboxMode;
  networkEgress: 'none' | 'allow_list';
  allowedDomains: string[];
  approvalRequiredFor: RiskLevel[];
  auditLogging: boolean;
}

export interface Person {
  id: ID;
  name: string;
}

export interface Agent {
  id: ID;
  name: string;
  description: string;
  category: AgentCategory;
  tags: string[];
  version: string;
  status: AgentStatus;
  verification: VerificationStatus;
  riskLevel: RiskLevel;
  /** 0–100, higher is riskier. */
  riskScore: number;
  creator: Person;
  owner: Person;
  createdAt: ISODate;
  updatedAt: ISODate;
  lastExecutionAt: ISODate | null;
  model: ModelConfig;
  tools: string[];
  permissions: AgentPermission[];
  resourceLimits: ResourceLimits;
  securityPolicy: SecurityPolicy;
  versions: AgentVersion[];
  securityChecks: SecurityCheck[];
}

export interface MarketplaceListing {
  id: ID;
  agentId: ID;
  name: string;
  summary: string;
  category: AgentCategory;
  tags: string[];
  publisher: string;
  verified: boolean;
  /** Demo security rating 0–100 (higher is safer). Not a real scan result. */
  securityRating: number;
  riskLevel: RiskLevel;
  /** Demo rating, 0–5. */
  rating: number;
  ratingCount: number;
  /** Demo usage count. Not real installs or users. */
  demoUsageCount: number;
  publishedAt: ISODate;
  popular: boolean;
}

export type ExecutionStatus =
  | 'QUEUED'
  | 'STARTING'
  | 'RUNNING'
  | 'WAITING_FOR_TOOL'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'TIMEOUT';

export const EXECUTION_STATUSES: readonly ExecutionStatus[] = [
  'QUEUED',
  'STARTING',
  'RUNNING',
  'WAITING_FOR_TOOL',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'TIMEOUT',
];

export interface TokenUsage {
  input: number;
  output: number;
}

export interface Execution {
  id: ID;
  agentId: ID;
  agentName: string;
  status: ExecutionStatus;
  trigger: 'manual' | 'schedule' | 'api';
  startedAt: ISODate;
  endedAt: ISODate | null;
  durationMs: number | null;
  model: string;
  tokenUsage: TokenUsage;
  toolCallCount: number;
  resultSummary: string | null;
}

export type TimelineEventKind = 'lifecycle' | 'model' | 'tool' | 'policy' | 'error' | 'result';

export interface TimelineEvent {
  id: ID;
  at: ISODate;
  kind: TimelineEventKind;
  label: string;
  detail?: string;
}

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  id: ID;
  at: ISODate;
  level: LogLevel;
  message: string;
}

export type ToolCallStatus = 'succeeded' | 'failed' | 'denied' | 'pending';

export interface ToolCall {
  id: ID;
  tool: string;
  status: ToolCallStatus;
  startedAt: ISODate;
  durationMs: number | null;
  inputSummary: string;
  outputSummary: string | null;
}

export interface ExecutionError {
  code: string;
  message: string;
}

export interface ExecutionDetail extends Execution {
  timeline: TimelineEvent[];
  logs: LogEntry[];
  toolCalls: ToolCall[];
  error: ExecutionError | null;
  result: string | null;
}

export type SecurityEventStatus = 'open' | 'investigating' | 'resolved';

export interface SecurityEvent {
  id: ID;
  severity: RiskLevel;
  type: string;
  agentId: ID | null;
  agentName: string;
  description: string;
  detectedAt: ISODate;
  status: SecurityEventStatus;
}

export type PolicyEnforcement = 'enforced' | 'monitoring' | 'disabled';

export interface PlatformPolicy {
  id: ID;
  name: string;
  description: string;
  enforcement: PolicyEnforcement;
}

export interface PermissionOverviewRow {
  capability: CapabilityKey;
  allowed: number;
  restricted: number;
  requiresApproval: number;
  denied: number;
}

export interface SecurityOverview {
  riskDistribution: Record<RiskLevel, number>;
  checks: Record<SecurityCheckStatus, number>;
  permissions: PermissionOverviewRow[];
  openAlerts: number;
}

export type ComponentState = 'operational' | 'degraded' | 'outage';

export interface SystemComponentStatus {
  id: 'api' | 'runtime' | 'database' | 'security';
  name: string;
  state: ComponentState;
  detail: string;
}

export interface DashboardSummary {
  totalAgents: number;
  activeAgents: number;
  runningExecutions: number;
  completedExecutions: number;
  failedExecutions: number;
  securityAlerts: number;
}

export interface DailyPoint {
  date: ISODate;
  value: number;
}

export interface AnalyticsSummary {
  executionsPerDay: DailyPoint[];
  tokensPerDay: DailyPoint[];
  successRate: number;
  averageDurationMs: number;
  topAgents: { agentId: ID; name: string; executions: number }[];
  statusBreakdown: Record<ExecutionStatus, number>;
}

export interface UserProfile {
  id: ID;
  name: string;
  email: string;
  status: 'active' | 'disabled';
  timezone: string;
  createdAt: ISODate;
  lastLoginAt: ISODate | null;
}

/** Roles inside one organization, least privileged first. */
export type Role = 'viewer' | 'member' | 'admin' | 'owner';
export const ROLES: readonly Role[] = ['viewer', 'member', 'admin', 'owner'];

export const ROLE_LABELS: Record<Role, string> = {
  viewer: 'Viewer',
  member: 'Member',
  admin: 'Administrator',
  owner: 'Owner',
};

export interface Organization {
  id: ID;
  name: string;
  slug: string;
}

export interface OrganizationMembership {
  organization: Organization;
  role: Role;
}

/** Who the caller is and what they may do, as the backend sees it. */
export interface SessionInfo {
  user: UserProfile;
  organization: Organization;
  role: Role;
  memberships: OrganizationMembership[];
  expiresAt: ISODate;
}

export interface Member {
  id: ID;
  userId: ID;
  email: string;
  name: string;
  role: Role;
  status: 'active' | 'disabled';
  createdAt: ISODate;
  lastLoginAt: ISODate | null;
}

export interface BackendHealth {
  status: 'ok';
  service: string;
  version: string;
  message: string;
}
