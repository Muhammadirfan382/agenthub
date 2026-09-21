import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AgentDraft } from '@/services/contracts';
import type { Agent, AlertRecord, Execution } from '@/types/domain';
import { httpAgentService } from './agentApi';
import { ApiError } from './client';
import { createHttpServices } from './createHttpServices';
import { httpExecutionService } from './executionApi';
import { fetchComponentStatus, httpAlertService, httpAnalyticsService, httpSecurityService } from './insightsApi';

const agent: Agent = {
  id: 'agt_research_scout_1',
  name: 'Research Scout',
  description: 'Searches approved sources and writes cited briefs for the team.',
  category: 'research',
  tags: ['research'],
  version: '1.0.0',
  status: 'active',
  verification: 'verified',
  visibility: 'private',
  riskLevel: 'medium',
  riskScore: 42,
  creator: { id: 'usr_demo_current', name: 'Demo User' },
  owner: { id: 'usr_demo_current', name: 'Demo User' },
  createdAt: '2026-09-01T10:00:00Z',
  updatedAt: '2026-09-10T10:00:00Z',
  lastExecutionAt: null,
  model: { provider: 'Model gateway', model: 'balanced-large', temperature: 0.2, maxOutputTokens: 4096 },
  tools: ['web_search'],
  permissions: [
    { capability: 'web_access', level: 'restricted', requiresApproval: false, scope: 'Allow-listed domains', risk: 'medium' },
  ],
  resourceLimits: { maxRuntimeSeconds: 600, maxMemoryMb: 512, maxTokensPerRun: 60000, maxToolCalls: 40 },
  securityPolicy: {
    sandbox: 'strict',
    networkEgress: 'allow_list',
    allowedDomains: ['arxiv.org'],
    approvalRequiredFor: ['high', 'critical'],
    auditLogging: true,
  },
  securityChecks: [{ id: 'chk_permissions', name: 'Permission review', status: 'not_run', detail: 'Not run yet.' }],
};

const draft: AgentDraft = {
  name: agent.name,
  description: agent.description,
  category: agent.category,
  tags: agent.tags,
  version: agent.version,
  model: agent.model,
  tools: agent.tools,
  permissions: agent.permissions,
  resourceLimits: agent.resourceLimits,
  securityPolicy: agent.securityPolicy,
};

const execution: Execution = {
  id: 'exe_1',
  agentId: agent.id,
  agentName: agent.name,
  status: 'QUEUED',
  trigger: 'manual',
  runtime: 'simulation',
  mode: 'simulated',
  modelRoute: null,
  estimatedCostUsd: null,
  startedAt: '2026-09-16T10:00:00Z',
  endedAt: null,
  durationMs: null,
  model: 'balanced-large',
  tokenUsage: { input: 0, output: 0 },
  toolCallCount: 0,
  resultSummary: null,
  requestedBy: 'Admin Person',
  budget: { maxRuntimeSeconds: 300, maxTokens: 50000, maxToolCalls: 20 },
  cancelRequested: false,
  pendingApprovals: 0,
};

const firingAlert: AlertRecord = {
  id: 'alr_1',
  rule: 'runs_failing',
  severity: 'warning',
  state: 'firing',
  summary: '3 runs failed in the last 15 minutes.',
  detail: { failed: 3 },
  firstSeen: '2026-09-20T10:00:00Z',
  lastSeen: '2026-09-20T10:05:00Z',
  resolvedAt: null,
  occurrences: 2,
};

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 200, offset: 0 });

/** Queues one response per call, in order. */
function stubFetch(...responses: { status?: number; body?: unknown }[]) {
  const fetchMock = vi.fn(() => {
    const next = responses.shift() ?? { status: 200, body: {} };
    const status = next.status ?? 200;
    return Promise.resolve({
      ok: status < 400,
      status,
      json: () => (next.body === undefined ? Promise.reject(new Error('no body')) : Promise.resolve(next.body)),
    } as Response);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function requestOf(fetchMock: ReturnType<typeof stubFetch>, index = 0) {
  const call = fetchMock.mock.calls[index] as unknown as [string, RequestInit];
  return { url: call[0], init: call[1] };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('http agent service', () => {
  it('sends only the filters that narrow the list', async () => {
    const fetchMock = stubFetch({ body: page([agent]) });

    await expect(httpAgentService.list({ search: '  scout ', status: 'all', risk: 'high', sort: 'name_asc' })).resolves.toEqual([agent]);

    const { url } = requestOf(fetchMock);
    expect(url).toContain('search=scout');
    expect(url).toContain('risk=high');
    expect(url).toContain('sort=name_asc');
    expect(url).not.toContain('status=');
    expect(url).not.toContain('category=');
  });

  it('treats a missing agent as null and keeps other failures as errors', async () => {
    stubFetch({ status: 404, body: { code: 'not_found', message: 'Agent not found.' } });
    await expect(httpAgentService.get('agt_missing')).resolves.toBeNull();

    stubFetch({ status: 500, body: { code: 'internal_error', message: 'Something went wrong.' } });
    await expect(httpAgentService.get('agt_x')).rejects.toBeInstanceOf(ApiError);
  });

  it('reports the API error message so the form can show it', async () => {
    stubFetch({ status: 409, body: { code: 'conflict', message: 'An agent named "Research Scout" already exists.' } });

    const error = await httpAgentService.create(draft).catch((e: unknown) => e);

    expect(error).toMatchObject({ status: 409, code: 'conflict', message: 'An agent named "Research Scout" already exists.' });
  });

  it('rejects a response that does not match the agent contract', async () => {
    stubFetch({ body: page([{ ...agent, riskLevel: 'catastrophic' }]) });

    await expect(httpAgentService.list()).rejects.toMatchObject({ code: 'invalid_response' });
  });

  it('uses the documented method and body for each write', async () => {
    const fetchMock = stubFetch({ body: agent }, { status: 204 }, { status: 202, body: execution });

    await httpAgentService.setStatus(agent.id, 'paused');
    await httpAgentService.remove(agent.id);
    await httpAgentService.requestExecution(agent.id);

    const status = requestOf(fetchMock, 0);
    expect(status.url).toBe(`/api/v1/agents/${agent.id}/status`);
    expect(status.init.method).toBe('PATCH');
    expect(status.init.body).toBe(JSON.stringify({ status: 'paused' }));

    expect(requestOf(fetchMock, 1).init.method).toBe('DELETE');

    const run = requestOf(fetchMock, 2);
    expect(run.url).toBe(`/api/v1/agents/${agent.id}/executions`);
    expect(run.init.method).toBe('POST');
  });

  it('escapes identifiers taken from the URL', async () => {
    const fetchMock = stubFetch({ status: 404, body: { code: 'not_found', message: 'Agent not found.' } });

    await httpAgentService.get('../../secrets');

    expect(requestOf(fetchMock).url).toBe('/api/v1/agents/..%2F..%2Fsecrets');
  });
});

describe('http execution service', () => {
  it('filters by agent and status', async () => {
    const fetchMock = stubFetch({ body: page([execution]) });

    await expect(httpExecutionService.list({ agentId: agent.id, status: 'QUEUED' })).resolves.toEqual([execution]);

    const { url } = requestOf(fetchMock);
    expect(url).toContain(`agentId=${agent.id}`);
    expect(url).toContain('status=QUEUED');
  });

  it('returns null for an execution that does not exist', async () => {
    stubFetch({ status: 404, body: { code: 'not_found', message: 'Execution not found.' } });

    await expect(httpExecutionService.get('exe_missing')).resolves.toBeNull();
  });
});

describe('api mode services', () => {
  it('declares which resources are real', () => {
    const services = createHttpServices();

    expect(services.dataSource).toBe('api');
    expect(services.liveResources).toEqual([
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
    ]);
  });

  it('counts the dashboard from live agents and executions', async () => {
    stubFetch(
      { body: page([agent, { ...agent, id: 'agt_2', status: 'paused' }]) },
      { body: page([execution, { ...execution, id: 'exe_2', status: 'COMPLETED' }, { ...execution, id: 'exe_3', status: 'FAILED' }]) },
      { body: page([firingAlert]) },
    );

    const summary = await createHttpServices().system.dashboardSummary();

    expect(summary).toMatchObject({
      totalAgents: 2,
      activeAgents: 1,
      runningExecutions: 1,
      completedExecutions: 1,
      failedExecutions: 1,
      securityAlerts: 1,
    });
  });
});

describe('http insight services', () => {
  it('reads alerts by state and resolves by id', async () => {
    const fetchMock = stubFetch(
      { body: page([firingAlert]) },
      { body: { ...firingAlert, state: 'resolved', resolvedAt: '2026-09-20T11:00:00Z' } },
    );

    expect(await httpAlertService.list('firing')).toEqual([firingAlert]);
    const resolved = await httpAlertService.resolve('alr/1');

    expect(requestOf(fetchMock, 0).url).toContain('/api/v1/alerts?limit=100&state=firing');
    expect(requestOf(fetchMock, 1).url).toContain('/api/v1/alerts/alr%2F1/resolve');
    expect(requestOf(fetchMock, 1).init.method).toBe('POST');
    expect(resolved.state).toBe('resolved');
  });

  it('reads component status from the live check', async () => {
    stubFetch({
      body: {
        state: 'degraded',
        checkedAt: '2026-09-20T10:00:00Z',
        components: [
          { id: 'database', name: 'Database', state: 'operational', detail: 'Answering queries.' },
          { id: 'sandbox', name: 'Sandbox', state: 'degraded', detail: 'No container runtime.' },
        ],
      },
    });

    const components = await fetchComponentStatus();

    expect(components.map((c) => [c.id, c.state])).toEqual([
      ['database', 'operational'],
      ['sandbox', 'degraded'],
    ]);
  });

  it('fills statuses the backend did not report with zero', async () => {
    stubFetch({
      body: {
        executionsPerDay: [{ date: '2026-09-20', value: 2 }],
        tokensPerDay: [{ date: '2026-09-20', value: 1200 }],
        successRate: 0.5,
        averageDurationMs: 2000,
        topAgents: [],
        statusBreakdown: { COMPLETED: 1, FAILED: 1 },
        estimatedCostUsd: 0.12,
      },
    });

    const summary = await httpAnalyticsService.summary();

    expect(summary.statusBreakdown.COMPLETED).toBe(1);
    expect(summary.statusBreakdown.RUNNING).toBe(0);
    expect(summary.estimatedCostUsd).toBe(0.12);
  });

  it('rejects security events that do not match the contract', async () => {
    stubFetch({ body: [{ id: 'evt_1', severity: 'catastrophic' }] });

    await expect(httpSecurityService.events()).rejects.toThrow();
  });

  it('states platform policies without fetching them', async () => {
    const fetchMock = stubFetch();

    const policies = await httpSecurityService.policies();

    expect(policies.length).toBeGreaterThan(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
