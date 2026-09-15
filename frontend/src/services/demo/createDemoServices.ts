import {
  buildDemoExecutionDetail,
  demoAgents,
  demoComponentStatus,
  demoExecutions,
  demoExecutionsPerDay,
  demoMarketplaceListings,
  demoPolicies,
  demoSecurityEvents,
  demoTokensPerDay,
  demoUser,
} from '@/features/demo';
import { deriveRisk } from '@/lib/risk';
import type {
  AgentService,
  AnalyticsService,
  AuthService,
  ExecutionService,
  MarketplaceService,
  SecurityService,
  Services,
  SystemService,
} from '@/services/contracts';
import { fetchBackendHealth } from '@/services/http/systemApi';
import type {
  Agent,
  CapabilityKey,
  Execution,
  ExecutionStatus,
  PermissionOverviewRow,
  RiskLevel,
  SecurityCheckStatus,
} from '@/types/domain';
import { EXECUTION_STATUSES } from '@/types/domain';

export interface DemoServiceOptions {
  /** Simulated network latency so loading states are visible. Tests use 0. */
  latencyMs?: number;
}

/**
 * DEMO implementation of every service contract.
 *
 * Data lives in memory for the lifetime of the page. Mutations (create, edit,
 * delete, execute) change only this in-memory copy and are lost on reload.
 * Nothing is sent to a server and no agent is executed.
 */
export function createDemoServices({ latencyMs = 350 }: DemoServiceOptions = {}): Services {
  const agents: Agent[] = structuredClone(demoAgents);
  const executions: Execution[] = structuredClone(demoExecutions);
  const listings = structuredClone(demoMarketplaceListings);
  const events = structuredClone(demoSecurityEvents);
  const policies = structuredClone(demoPolicies);
  let user = structuredClone(demoUser);
  let counter = 0;

  const respond = <T>(value: T): Promise<T> =>
    new Promise((resolve) => setTimeout(() => resolve(structuredClone(value)), latencyMs));

  const fail = (message: string): Promise<never> =>
    new Promise((_, reject) => setTimeout(() => reject(new Error(message)), latencyMs));

  const findAgent = (id: string) => agents.find((a) => a.id === id);

  const agentService: AgentService = {
    list(params = {}) {
      const search = params.search?.trim().toLowerCase() ?? '';
      let result = agents.filter((agent) => {
        if (params.status && params.status !== 'all' && agent.status !== params.status) return false;
        if (params.risk && params.risk !== 'all' && agent.riskLevel !== params.risk) return false;
        if (params.category && params.category !== 'all' && agent.category !== params.category) return false;
        if (!search) return true;
        return [agent.name, agent.description, agent.creator.name, ...agent.tags].some((field) =>
          field.toLowerCase().includes(search),
        );
      });
      const sort = params.sort ?? 'updated_desc';
      result = [...result].sort((a, b) => {
        switch (sort) {
          case 'name_asc':
            return a.name.localeCompare(b.name);
          case 'risk_desc':
            return b.riskScore - a.riskScore;
          case 'last_execution_desc':
            return (b.lastExecutionAt ?? '').localeCompare(a.lastExecutionAt ?? '');
          case 'updated_desc':
            return b.updatedAt.localeCompare(a.updatedAt);
        }
      });
      return respond(result);
    },

    get(id) {
      return respond(findAgent(id) ?? null);
    },

    create(draft) {
      counter += 1;
      const now = new Date().toISOString();
      const slug = draft.name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'agent';
      const risk = deriveRisk(draft.permissions);
      const agent: Agent = {
        ...draft,
        id: `agt_demo_${slug}_${counter}`,
        status: 'draft',
        verification: 'unverified',
        riskLevel: risk.level,
        riskScore: risk.score,
        creator: { id: user.id, name: user.name },
        owner: { id: user.id, name: user.name },
        createdAt: now,
        updatedAt: now,
        lastExecutionAt: null,
        versions: [{ version: draft.version, releasedAt: now, status: 'draft', changes: ['Created in AgentHub (demo, not saved to a server)'] }],
        securityChecks: [
          { id: 'chk_dependencies', name: 'Dependency vulnerability scan', status: 'not_run', detail: 'Not yet evaluated.' },
          { id: 'chk_secrets', name: 'Embedded secret detection', status: 'not_run', detail: 'Not yet evaluated.' },
          { id: 'chk_permissions', name: 'Permission minimisation', status: 'not_run', detail: 'Not yet evaluated.' },
          { id: 'chk_injection', name: 'Prompt-injection evaluation', status: 'not_run', detail: 'Not yet evaluated.' },
          { id: 'chk_egress', name: 'Network egress policy', status: 'not_run', detail: 'Not yet evaluated.' },
        ],
      };
      agents.unshift(agent);
      return respond(agent);
    },

    update(id, draft) {
      const index = agents.findIndex((a) => a.id === id);
      const existing = agents[index];
      if (!existing) return fail('Agent not found.');
      const risk = deriveRisk(draft.permissions);
      const updated: Agent = { ...existing, ...draft, riskLevel: risk.level, riskScore: risk.score, updatedAt: new Date().toISOString() };
      agents[index] = updated;
      return respond(updated);
    },

    remove(id) {
      const index = agents.findIndex((a) => a.id === id);
      if (index === -1) return fail('Agent not found.');
      agents.splice(index, 1);
      return respond(undefined);
    },

    setStatus(id, status) {
      const agent = findAgent(id);
      if (!agent) return fail('Agent not found.');
      agent.status = status;
      agent.updatedAt = new Date().toISOString();
      return respond(agent);
    },

    requestExecution(id) {
      const agent = findAgent(id);
      if (!agent) return fail('Agent not found.');
      if (agent.status !== 'active') {
        return fail(`${agent.name} is ${agent.status} and cannot be executed.`);
      }
      counter += 1;
      const execution: Execution = {
        id: `exe_demo_${Date.now().toString(16)}${counter}`,
        agentId: agent.id,
        agentName: agent.name,
        status: 'QUEUED',
        trigger: 'manual',
        startedAt: new Date().toISOString(),
        endedAt: null,
        durationMs: null,
        model: agent.model.model,
        tokenUsage: { input: 0, output: 0 },
        toolCallCount: 0,
        resultSummary: null,
      };
      executions.unshift(execution);
      return respond(execution);
    },
  };

  const marketplaceService: MarketplaceService = {
    list(params = {}) {
      const search = params.search?.trim().toLowerCase() ?? '';
      let result = listings.filter((listing) => {
        if (params.category && params.category !== 'all' && listing.category !== params.category) return false;
        if (params.tag && !listing.tags.includes(params.tag)) return false;
        if (params.collection === 'verified' && !listing.verified) return false;
        if (params.collection === 'popular' && !listing.popular) return false;
        if (!search) return true;
        return [listing.name, listing.summary, listing.publisher, ...listing.tags].some((f) => f.toLowerCase().includes(search));
      });
      result = [...result].sort((a, b) =>
        params.collection === 'recent' ? b.publishedAt.localeCompare(a.publishedAt) : b.demoUsageCount - a.demoUsageCount,
      );
      return respond(result);
    },
    tags() {
      return respond([...new Set(listings.flatMap((l) => l.tags))].sort());
    },
  };

  const executionService: ExecutionService = {
    list(params = {}) {
      const search = params.search?.trim().toLowerCase() ?? '';
      const result = executions
        .filter((e) => (params.status && params.status !== 'all' ? e.status === params.status : true))
        .filter((e) => (params.agentId ? e.agentId === params.agentId : true))
        .filter((e) => !search || e.id.toLowerCase().includes(search) || e.agentName.toLowerCase().includes(search))
        .sort((a, b) => b.startedAt.localeCompare(a.startedAt));
      return respond(result);
    },
    get(id) {
      const execution = executions.find((e) => e.id === id);
      return respond(execution ? buildDemoExecutionDetail(execution) : null);
    },
  };

  const openAlerts = () => events.filter((e) => e.status !== 'resolved').length;

  const securityService: SecurityService = {
    overview() {
      const riskDistribution: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0, critical: 0 };
      const checks: Record<SecurityCheckStatus, number> = { passed: 0, warning: 0, failed: 0, not_run: 0 };
      const rows = new Map<CapabilityKey, PermissionOverviewRow>();
      for (const agent of agents) {
        riskDistribution[agent.riskLevel] += 1;
        for (const check of agent.securityChecks) checks[check.status] += 1;
        for (const p of agent.permissions) {
          const row = rows.get(p.capability) ?? { capability: p.capability, allowed: 0, restricted: 0, requiresApproval: 0, denied: 0 };
          if (p.level === 'denied') row.denied += 1;
          else if (p.level === 'allowed') row.allowed += 1;
          else row.restricted += 1;
          if (p.level !== 'denied' && p.requiresApproval) row.requiresApproval += 1;
          rows.set(p.capability, row);
        }
      }
      return respond({ riskDistribution, checks, permissions: [...rows.values()], openAlerts: openAlerts() });
    },
    events() {
      return respond([...events].sort((a, b) => b.detectedAt.localeCompare(a.detectedAt)));
    },
    policies() {
      return respond(policies);
    },
  };

  const countStatus = (statuses: ExecutionStatus[]) => executions.filter((e) => statuses.includes(e.status)).length;

  const systemService: SystemService = {
    dashboardSummary() {
      return respond({
        totalAgents: agents.length,
        activeAgents: agents.filter((a) => a.status === 'active').length,
        runningExecutions: countStatus(['STARTING', 'RUNNING', 'WAITING_FOR_TOOL']),
        completedExecutions: countStatus(['COMPLETED']),
        failedExecutions: countStatus(['FAILED', 'TIMEOUT']),
        securityAlerts: openAlerts(),
      });
    },
    componentStatus() {
      return respond(demoComponentStatus);
    },
    checkBackendHealth() {
      return fetchBackendHealth();
    },
  };

  const analyticsService: AnalyticsService = {
    summary() {
      const finished = executions.filter((e) => ['COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED'].includes(e.status));
      const completed = finished.filter((e) => e.status === 'COMPLETED');
      const withDuration = executions.filter((e) => e.durationMs !== null);
      const byAgent = new Map<string, { agentId: string; name: string; executions: number }>();
      for (const e of executions) {
        const entry = byAgent.get(e.agentId) ?? { agentId: e.agentId, name: e.agentName, executions: 0 };
        entry.executions += 1;
        byAgent.set(e.agentId, entry);
      }
      const statusBreakdown = Object.fromEntries(EXECUTION_STATUSES.map((s) => [s, countStatus([s])])) as Record<ExecutionStatus, number>;
      return respond({
        executionsPerDay: demoExecutionsPerDay,
        tokensPerDay: demoTokensPerDay,
        successRate: finished.length ? completed.length / finished.length : 0,
        averageDurationMs: withDuration.length
          ? withDuration.reduce((sum, e) => sum + (e.durationMs ?? 0), 0) / withDuration.length
          : 0,
        topAgents: [...byAgent.values()].sort((a, b) => b.executions - a.executions).slice(0, 5),
        statusBreakdown,
      });
    },
  };

  const authService: AuthService = {
    currentUser() {
      return respond(user);
    },
    updateProfile(update) {
      user = { ...user, ...update };
      return respond(user);
    },
  };

  return {
    dataSource: 'demo',
    agents: agentService,
    marketplace: marketplaceService,
    executions: executionService,
    security: securityService,
    system: systemService,
    analytics: analyticsService,
    auth: authService,
  };
}
