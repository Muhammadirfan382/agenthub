import type { DashboardSummary } from '@/types/domain';
import type { Services, SystemService } from '../contracts';
import { createDemoServices } from '../demo/createDemoServices';
import { httpAgentService } from './agentApi';
import { httpAuthService, httpMemberService } from './authApi';
import { httpExecutionService } from './executionApi';
import { httpInstallationService, httpMarketplaceService } from './registryApi';
import { fetchBackendHealth } from './systemApi';

/**
 * API mode.
 *
 * The backend implements identity, agents, executions and the registry
 * (versions, marketplace listings and installations). Security and analytics
 * still come from the demo services, and the UI says so: `liveResources` is
 * the single source of truth for that claim.
 */
function createSystemService(demo: SystemService): SystemService {
  return {
    ...demo,

    /** Counted from real agents and executions, so it cannot contradict those pages. */
    async dashboardSummary(): Promise<DashboardSummary> {
      const [agents, executions, demoSummary] = await Promise.all([
        httpAgentService.list(),
        httpExecutionService.list(),
        demo.dashboardSummary(),
      ]);
      const countStatus = (...statuses: string[]) =>
        executions.filter((execution) => statuses.includes(execution.status)).length;

      return {
        totalAgents: agents.length,
        activeAgents: agents.filter((agent) => agent.status === 'active').length,
        runningExecutions: countStatus('QUEUED', 'STARTING', 'RUNNING', 'WAITING_FOR_TOOL'),
        completedExecutions: countStatus('COMPLETED'),
        failedExecutions: countStatus('FAILED', 'TIMEOUT'),
        // Security monitoring does not exist yet; this stays demonstration data.
        securityAlerts: demoSummary.securityAlerts,
      };
    },

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
    ],
    agents: httpAgentService,
    executions: httpExecutionService,
    system: createSystemService(demo.system),
    auth: httpAuthService,
    members: httpMemberService,
    marketplace: httpMarketplaceService,
    installations: httpInstallationService,
  };
}
