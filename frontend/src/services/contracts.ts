import type {
  Agent,
  AgentCategory,
  AgentPermission,
  AgentStatus,
  AnalyticsSummary,
  BackendHealth,
  DashboardSummary,
  Execution,
  ExecutionDetail,
  ExecutionStatus,
  ID,
  MarketplaceListing,
  ModelConfig,
  PlatformPolicy,
  ResourceLimits,
  RiskLevel,
  SecurityEvent,
  SecurityOverview,
  SecurityPolicy,
  SystemComponentStatus,
  UserProfile,
} from '@/types/domain';

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
  requestExecution(id: ID): Promise<Execution>;
}

export type MarketplaceCollection = 'all' | 'verified' | 'popular' | 'recent';

export interface MarketplaceParams {
  search?: string;
  category?: AgentCategory | 'all';
  tag?: string;
  collection?: MarketplaceCollection;
}

export interface MarketplaceService {
  list(params?: MarketplaceParams): Promise<MarketplaceListing[]>;
  tags(): Promise<string[]>;
}

export interface ExecutionListParams {
  status?: ExecutionStatus | 'all';
  agentId?: ID;
  search?: string;
}

export interface ExecutionService {
  list(params?: ExecutionListParams): Promise<Execution[]>;
  get(id: ID): Promise<ExecutionDetail | null>;
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
  email: string;
  timezone: string;
}

/**
 * Placeholder. There is no authentication in Phase 1. The "current user" is a
 * demo profile, and nothing here is a security control.
 */
export interface AuthService {
  currentUser(): Promise<UserProfile>;
  updateProfile(update: ProfileUpdate): Promise<UserProfile>;
}

export type DataSource = 'demo';

export interface Services {
  dataSource: DataSource;
  agents: AgentService;
  marketplace: MarketplaceService;
  executions: ExecutionService;
  security: SecurityService;
  system: SystemService;
  analytics: AnalyticsService;
  auth: AuthService;
}
