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
  visibility: Visibility;
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
  securityChecks: SecurityCheck[];
}

/** How widely an agent is listed. Private is the default. */
export type Visibility = 'private' | 'organization' | 'public';

export const VISIBILITY_LABELS: Record<Visibility, string> = {
  private: 'Private',
  organization: 'Organization',
  public: 'Public',
};

export type VersionStatus = 'draft' | 'published' | 'deprecated';

/**
 * What a published version asks for. Frozen at publish time: editing the agent
 * afterwards changes the next version, never this one.
 */
export interface AgentManifest {
  name: string;
  description: string;
  category: AgentCategory;
  tags: string[];
  version: string;
  model: ModelConfig;
  tools: string[];
  /** Requests, not grants. An installing organization decides what to allow. */
  requiredPermissions: AgentPermission[];
  resourceLimits: ResourceLimits;
  securityPolicy: SecurityPolicy;
}

export interface AgentVersion {
  id: ID;
  agentId: ID;
  version: string;
  status: VersionStatus;
  riskLevel: RiskLevel;
  riskScore: number;
  changelog: string[];
  manifest: AgentManifest;
  createdAt: ISODate;
  publishedAt: ISODate | null;
  deprecatedAt: ISODate | null;
  createdBy: string;
}

/** Invented popularity numbers, present only in demo mode. */
export interface DemoListingStats {
  rating: number;
  ratingCount: number;
  usageCount: number;
  securityRating: number;
}

export interface MarketplaceListing {
  /** The published version's id: a listing is a version, not an agent. */
  id: ID;
  agentId: ID;
  name: string;
  summary: string;
  category: AgentCategory;
  tags: string[];
  version: string;
  publisher: string;
  verification: VerificationStatus;
  visibility: Visibility;
  riskLevel: RiskLevel;
  riskScore: number;
  tools: string[];
  publishedAt: ISODate;
  installed: boolean;
  installationId: ID | null;
  /** True when the listing was published by your own organization. */
  own: boolean;
  demoStats?: DemoListingStats;
}

export interface MarketplaceListingDetail extends MarketplaceListing {
  manifest: AgentManifest;
  changelog: string[];
}

/** One capability an organization allows an installed agent to use. */
export type PermissionGrant = AgentPermission;

export type InstallationStatus = 'active' | 'suspended';

export interface Installation {
  id: ID;
  agentId: ID;
  agentVersionId: ID;
  agentName: string;
  publisher: string;
  version: string;
  status: InstallationStatus;
  grants: PermissionGrant[];
  riskLevel: RiskLevel;
  riskScore: number;
  note: string | null;
  installedBy: string;
  createdAt: ISODate;
  updatedAt: ISODate;
  /** Manifest tools whose capability was not granted: they cannot work. */
  unusableTools: string[];
  updateAvailable: boolean;
}

export interface InstallationDetail extends Installation {
  manifest: AgentManifest;
}

export type ExecutionStatus =
  | 'QUEUED'
  | 'STARTING'
  | 'RUNNING'
  | 'WAITING_FOR_TOOL'
  | 'WAITING_FOR_APPROVAL'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'TIMEOUT';

export const EXECUTION_STATUSES: readonly ExecutionStatus[] = [
  'QUEUED',
  'STARTING',
  'RUNNING',
  'WAITING_FOR_TOOL',
  'WAITING_FOR_APPROVAL',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'TIMEOUT',
];

/** Statuses a run can never leave. */
export const TERMINAL_EXECUTION_STATUSES: readonly ExecutionStatus[] = [
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'TIMEOUT',
];

export function isExecutionFinished(status: ExecutionStatus): boolean {
  return TERMINAL_EXECUTION_STATUSES.includes(status);
}

/**
 * What produced a run. Only `simulation` exists: there is no sandbox and no
 * model gateway yet, so no agent code is executed.
 */
export type ExecutionRuntime = 'simulation';

export interface ExecutionBudget {
  maxRuntimeSeconds: number;
  maxTokens: number;
  maxToolCalls: number;
}

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
  runtime: ExecutionRuntime;
  startedAt: ISODate;
  endedAt: ISODate | null;
  durationMs: number | null;
  model: string;
  tokenUsage: TokenUsage;
  toolCallCount: number;
  resultSummary: string | null;
  requestedBy: string;
  budget: ExecutionBudget;
  cancelRequested: boolean;
  pendingApprovals: number;
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

/** Never "succeeded" while the runtime is a simulation: nothing ran. */
export type ToolCallStatus = 'pending' | 'simulated' | 'denied' | 'failed';

export interface ToolCall {
  id: ID;
  tool: string;
  capability: string;
  status: ToolCallStatus;
  startedAt: ISODate;
  durationMs: number | null;
  inputSummary: string;
  outputSummary: string | null;
}

export type ApprovalStatus = 'pending' | 'approved' | 'denied';
export type ApprovalDecision = 'approved' | 'denied';

/** A paused step: somebody has to decide before the run continues. */
export interface Approval {
  id: ID;
  executionId: ID;
  agentName: string;
  capability: string;
  tool: string | null;
  reason: string;
  riskLevel: RiskLevel;
  status: ApprovalStatus;
  requestedAt: ISODate;
  decidedAt: ISODate | null;
  decidedBy: string | null;
  note: string | null;
  automatic: boolean;
}

/** The organization-wide stop control. */
export interface RuntimeState {
  executionsPaused: boolean;
  pausedAt: ISODate | null;
  pausedBy: string | null;
  reason: string | null;
  pendingApprovals: number;
}

export interface ExecutionError {
  code: string;
  message: string;
}

export interface ExecutionDetail extends Execution {
  timeline: TimelineEvent[];
  logs: LogEntry[];
  toolCalls: ToolCall[];
  approvals: Approval[];
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
