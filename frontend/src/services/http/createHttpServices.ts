import type { DashboardSummary } from '@/types/domain';
import type { Services, SystemService } from '../contracts';
import { createDemoServices } from '../demo/createDemoServices';
import { httpAgentService } from './agentApi';
import { httpAuthService, httpMemberService } from './authApi';
import { httpAuditService } from './auditApi';
import { httpExecutionService, httpRuntimeService } from './executionApi';
import { httpInstallationService, httpMarketplaceService } from './registryApi';
import {
  fetchComponentStatus,
  httpAlertService,
  httpAnalyticsService,
  httpSecurityService,
} from './insightsApi';
import { fetchBackendHealth } from './systemApi';

/**
 * API mode.
 *
 * The backend implements everything the UI reads, including security,
 * analytics, component status and alerts (Phase 9). `liveResources` remains
 * the single source of truth for what is real in this mode.
 */
function createSystemService(demo: SystemService): SystemService {
  return {
    ...demo,

    /** Counted from real agents and executions, so it cannot contradict those pages. */
    async dashboardSummary(): Promise<DashboardSummary> {
      const [agents, executions, firing] = await Promise.all([
        httpAgentService.list(),
        httpExecutionService.list(),
        httpAlertService.list('firing'),
      ]);
      const countStatus = (...statuses: string[]) =>
        executions.filter((execution) => statuses.includes(execution.status)).length;

      return {
        totalAgents: agents.length,
        activeAgents: agents.filter((agent) => agent.status === 'active').length,
        runningExecutions: countStatus('QUEUED', 'STARTING', 'RUNNING', 'WAITING_FOR_TOOL'),
        completedExecutions: countStatus('COMPLETED'),
        failedExecutions: countStatus('FAILED', 'TIMEOUT'),
        securityAlerts: firing.length,
      };
    },

    componentStatus: fetchComponentStatus,
    checkBackendHealth: fetchBackendHealth,
  };
}

export function createHttpServices(): Services {
  const demo = createDemoServices();
  return {
    ...demo,
    dataSource: 'api',
    liveResources: [
      'agents',
      'executions',
      'dashboard',
      'members',
      'marketplace',
      'installations',
      'runtime',
      'audit',
      'security',
      'analytics',
      'status',
      'alerts',
    ],
    agents: httpAgentService,
    executions: httpExecutionService,
    system: createSystemService(demo.system),
    auth: httpAuthService,
    members: httpMemberService,
    marketplace: httpMarketplaceService,
    installations: httpInstallationService,
    runtime: httpRuntimeService,
    audit: httpAuditService,
    security: httpSecurityService,
    analytics: httpAnalyticsService,
    alerts: httpAlertService,
  };
}
