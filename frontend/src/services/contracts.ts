import type {
  Agent,
  AgentCategory,
  AgentPermission,
  AgentVersion,
  Approval,
  ApprovalDecision,
  AgentStatus,
  AnalyticsSummary,
  BackendHealth,
  DashboardSummary,
  Execution,
  ExecutionDetail,
  ExecutionStatus,
  ID,
  Installation,
  InstallationDetail,
  MarketplaceListing,
  MarketplaceListingDetail,
  Member,
  ModelConfig,
  PermissionGrant,
  PlatformPolicy,
  ResourceLimits,
  RiskLevel,
  SecurityEvent,
  SecurityOverview,
  ModelGatewayStatus,
  RuntimeState,
  SandboxCheckResult,
  SandboxStatus,
  SecurityPolicy,
  SessionInfo,
  Visibility,
  SystemComponentStatus,
  UserProfile,
} from '@/types/domain';
import type { Role } from '@/types/domain';

/**
 * Service contracts. UI code depends only on these interfaces.
 *
 * Phase 1 ships demo implementations (src/services/demo). Phase 2 adds HTTP
 * implementations of the same interfaces; no component should need to change.
 */

export type AgentSort = 'updated_desc' | 'name_asc' | 'risk_desc' | 'last_execution_desc';

export interface AgentListParams {
  search?: string;
  status?: AgentStatus | 'all';
  risk?: RiskLevel | 'all';
  category?: AgentCategory | 'all';
  sort?: AgentSort;
}

/** Everything a user supplies when creating or editing an agent. */
export interface AgentDraft {
  name: string;
  description: string;
  category: AgentCategory;
  tags: string[];
  version: string;
  model: ModelConfig;
  tools: string[];
  permissions: AgentPermission[];
  resourceLimits: ResourceLimits;
  securityPolicy: SecurityPolicy;
}

export interface AgentService {
  list(params?: AgentListParams): Promise<Agent[]>;
  get(id: ID): Promise<Agent | null>;
  create(draft: AgentDraft): Promise<Agent>;
  update(id: ID, draft: AgentDraft): Promise<Agent>;
  remove(id: ID): Promise<void>;
  setStatus(id: ID, status: AgentStatus): Promise<Agent>;
  /** Requests an execution. Nothing actually runs until the Phase 5 runtime exists. */
  /** Queues a run. `input` is the task, sent to the model as the user's request. */
  requestExecution(id: ID, input?: string): Promise<Execution>;
  /** Published manifests, newest first. */
  versions(id: ID): Promise<AgentVersion[]>;
  /** Freezes the current configuration as a published version. */
  publish(id: ID, input: PublishInput): Promise<AgentVersion>;
  setVisibility(id: ID, visibility: Visibility): Promise<Agent>;
}

export interface PublishInput {
  changelog: string[];
  visibility?: Visibility;
}

/** Tabs over the same listings, not different data sets. */
export type MarketplaceCollection = 'all' | 'verified' | 'installed';

export interface MarketplaceParams {
  search?: string;
  category?: AgentCategory | 'all';
  tag?: string;
  collection?: MarketplaceCollection;
}

export interface MarketplaceService {
  list(params?: MarketplaceParams): Promise<MarketplaceListing[]>;
  get(id: ID): Promise<MarketplaceListingDetail | null>;
  tags(): Promise<string[]>;
}

export interface InstallInput {
  agentVersionId: ID;
  /** Capabilities left out are denied: nothing is granted implicitly. */
  grants: PermissionGrant[];
  note?: string | null;
}

export interface InstallationPatch {
  grants?: PermissionGrant[];
  status?: Installation['status'];
  note?: string | null;
}

export interface InstallationService {
  list(): Promise<Installation[]>;
  get(id: ID): Promise<InstallationDetail | null>;
  install(input: InstallInput): Promise<InstallationDetail>;
  update(id: ID, patch: InstallationPatch): Promise<InstallationDetail>;
  uninstall(id: ID): Promise<void>;
}

export interface ExecutionListParams {
  status?: ExecutionStatus | 'all';
  agentId?: ID;
  search?: string;
}

export interface ExecutionService {
  list(params?: ExecutionListParams): Promise<Execution[]>;
  get(id: ID): Promise<ExecutionDetail | null>;
  /** Asks the runtime to stop at the next step boundary. */
  cancel(id: ID): Promise<ExecutionDetail>;
  /** Approvals waiting on a person, across the organization. */
  pendingApprovals(): Promise<Approval[]>;
  decideApproval(
    executionId: ID,
    approvalId: ID,
    decision: ApprovalDecision,
    note?: string,
  ): Promise<ExecutionDetail>;
}

export interface RuntimeService {
  state(): Promise<RuntimeState>;
  /** The organization-wide stop: blocks new runs and stops running ones. */
  setExecutionsPaused(paused: boolean, reason?: string): Promise<RuntimeState>;
  /** The sandbox configuration and whether a container runtime answers. Starts nothing. */
  sandbox(): Promise<SandboxStatus>;
  /** Starts one throwaway container and reports each isolation guarantee. */
  checkSandbox(): Promise<SandboxCheckResult>;
  /** Model providers, tier routes, limits and today's usage. Never credentials. */
  models(): Promise<ModelGatewayStatus>;
}

export interface SecurityService {
  overview(): Promise<SecurityOverview>;
  events(): Promise<SecurityEvent[]>;
  policies(): Promise<PlatformPolicy[]>;
}

export interface SystemService {
  dashboardSummary(): Promise<DashboardSummary>;
  /** Demonstration component states until real health checks exist (Phase 2/9). */
  componentStatus(): Promise<SystemComponentStatus[]>;
  /** Real request to the backend liveness endpoint (`GET /api/v1/health`). */
  checkBackendHealth(): Promise<BackendHealth>;
}

export interface AnalyticsService {
  summary(): Promise<AnalyticsSummary>;
}

export interface ProfileUpdate {
  name: string;
  timezone: string;
}

export interface Credentials {
  email: string;
  password: string;
}

export interface PasswordChange {
  currentPassword: string;
  newPassword: string;
}

/**
 * Sessions. The backend owns them: the browser only holds an HttpOnly cookie
 * it cannot read, and every answer here comes from the server.
 */
export interface AuthService {
  /** The current session, or null when nobody is signed in. */
  session(): Promise<SessionInfo | null>;
  login(credentials: Credentials): Promise<SessionInfo>;
  logout(): Promise<void>;
  updateProfile(update: ProfileUpdate): Promise<UserProfile>;
  changePassword(change: PasswordChange): Promise<void>;
  switchOrganization(organizationId: ID): Promise<SessionInfo>;
}

export interface MemberService {
  list(): Promise<Member[]>;
  /** Adds an existing account to the organization; accounts are created out of band. */
  add(email: string, role: Role): Promise<Member>;
  setRole(id: ID, role: Role): Promise<Member>;
  remove(id: ID): Promise<void>;
}

export type DataSource = 'demo' | 'api';

/** Parts of the app the real backend can serve today. Everything else is demo data. */
export type LiveResource =
  | 'agents'
  | 'executions'
  | 'dashboard'
  | 'members'
  | 'marketplace'
  | 'installations'
  | 'runtime';

export interface Services {
  dataSource: DataSource;
  /** What the backend really serves in this mode, so the UI can say so accurately. */
  liveResources: readonly LiveResource[];
  agents: AgentService;
  marketplace: MarketplaceService;
  executions: ExecutionService;
  security: SecurityService;
  system: SystemService;
  analytics: AnalyticsService;
  auth: AuthService;
  members: MemberService;
  installations: InstallationService;
  runtime: RuntimeService;
}
