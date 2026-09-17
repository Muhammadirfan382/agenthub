import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AgentPermission, AgentVersion, Installation, MarketplaceListing } from '@/types/domain';
import { httpAgentService } from './agentApi';
import { httpInstallationService, httpMarketplaceService } from './registryApi';

const permission: AgentPermission = {
  capability: 'web_access',
  level: 'restricted',
  requiresApproval: false,
  scope: 'Allow-listed docs',
  risk: 'medium',
};

const manifest = {
  name: 'Research Scout',
  description: 'Finds and cites sources.',
  category: 'research' as const,
  tags: ['research'],
  version: '1.0.0',
  model: { provider: 'Model gateway', model: 'balanced-large', temperature: 0.2, maxOutputTokens: 4096 },
  tools: ['web_search'],
  requiredPermissions: [permission],
  resourceLimits: { maxRuntimeSeconds: 600, maxMemoryMb: 512, maxTokensPerRun: 60000, maxToolCalls: 40 },
  securityPolicy: {
    sandbox: 'strict' as const,
    networkEgress: 'allow_list' as const,
    allowedDomains: ['docs.example.com'],
    approvalRequiredFor: ['high' as const, 'critical' as const],
    auditLogging: true,
  },
};

const version: AgentVersion = {
  id: 'ver_1',
  agentId: 'agt_1',
  version: '1.0.0',
  status: 'published',
  riskLevel: 'medium',
  riskScore: 44,
  changelog: ['First release.'],
  manifest,
  createdAt: '2026-09-01T10:00:00Z',
  publishedAt: '2026-09-01T10:00:00Z',
  deprecatedAt: null,
  createdBy: 'Admin Person',
};

const listing: MarketplaceListing = {
  id: 'ver_1',
  agentId: 'agt_1',
  name: 'Research Scout',
  summary: 'Finds and cites sources.',
  category: 'research',
  tags: ['research'],
  version: '1.0.0',
  publisher: 'Other Workspace',
  verification: 'verified',
  visibility: 'public',
  riskLevel: 'medium',
  riskScore: 44,
  tools: ['web_search'],
  publishedAt: '2026-09-01T10:00:00Z',
  installed: false,
  installationId: null,
  own: false,
};

const installation: Installation = {
  id: 'ins_1',
  agentId: 'agt_1',
  agentVersionId: 'ver_1',
  agentName: 'Research Scout',
  publisher: 'Other Workspace',
  version: '1.0.0',
  status: 'active',
  grants: [permission],
  riskLevel: 'medium',
  riskScore: 44,
  note: null,
  installedBy: 'Admin Person',
  createdAt: '2026-09-10T10:00:00Z',
  updatedAt: '2026-09-10T10:00:00Z',
  unusableTools: [],
  updateAvailable: false,
};

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 200, offset: 0 });

function stubFetch(...responses: { status?: number; body?: unknown }[]) {
  const fetchMock = vi.fn(() => {
    const next = responses.shift() ?? { status: 200, body: {} };
    const status = next.status ?? 200;
    return Promise.resolve({
      ok: status < 400,
      status,
      json: () =>
        next.body === undefined ? Promise.reject(new Error('no body')) : Promise.resolve(next.body),
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

describe('versions', () => {
  it('reads and publishes versions for an agent', async () => {
    const fetchMock = stubFetch({ body: page([version]) }, { status: 201, body: version });

    await expect(httpAgentService.versions('agt_1')).resolves.toEqual([version]);
    await httpAgentService.publish('agt_1', {
      changelog: ['First release.'],
      visibility: 'public',
    });

    expect(requestOf(fetchMock, 0).url).toContain('/api/v1/agents/agt_1/versions');
    const publish = requestOf(fetchMock, 1);
    expect(publish.init.method).toBe('POST');
    expect(publish.init.body).toBe(
      JSON.stringify({ changelog: ['First release.'], visibility: 'public' }),
    );
  });

  it('changes visibility through its own endpoint', async () => {
    const fetchMock = stubFetch({ status: 422, body: { code: 'validation_failed', message: 'Publish a version first.' } });

    await expect(httpAgentService.setVisibility('agt_1', 'public')).rejects.toMatchObject({
      status: 422,
      message: 'Publish a version first.',
    });
    expect(requestOf(fetchMock).url).toBe('/api/v1/agents/agt_1/visibility');
  });
});

describe('marketplace', () => {
  it('passes filters to the API and keeps the server order', async () => {
    const fetchMock = stubFetch({ body: page([listing]) });

    await expect(
      httpMarketplaceService.list({ search: ' scout ', category: 'research', tag: 'research' }),
    ).resolves.toEqual([listing]);

    const { url } = requestOf(fetchMock);
    expect(url).toContain('search=scout');
    expect(url).toContain('category=research');
    expect(url).toContain('tag=research');
    expect(url).not.toContain('verified=');
  });

  it('asks for verified listings only when that collection is chosen', async () => {
    const fetchMock = stubFetch({ body: page([listing]) });

    await httpMarketplaceService.list({ collection: 'verified' });

    expect(requestOf(fetchMock).url).toContain('verified=true');
  });

  it('filters the installed collection from the same listings', async () => {
    stubFetch({ body: page([listing, { ...listing, id: 'ver_2', installed: true }]) });

    const installed = await httpMarketplaceService.list({ collection: 'installed' });

    expect(installed.map((entry) => entry.id)).toEqual(['ver_2']);
  });

  it('treats an unlisted version as not found', async () => {
    stubFetch({ status: 404, body: { code: 'not_found', message: 'No listing with this id.' } });

    await expect(httpMarketplaceService.get('ver_missing')).resolves.toBeNull();
  });
});

describe('installations', () => {
  it('sends the grants exactly as chosen', async () => {
    const fetchMock = stubFetch({ status: 201, body: { ...installation, manifest } });

    await httpInstallationService.install({
      agentVersionId: 'ver_1',
      grants: [permission],
      note: 'Trial install',
    });

    const { url, init } = requestOf(fetchMock);
    expect(url).toBe('/api/v1/installations');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({
      agentVersionId: 'ver_1',
      grants: [permission],
      note: 'Trial install',
    });
  });

  it('updates and removes an installation by id', async () => {
    const fetchMock = stubFetch({ body: { ...installation, manifest } }, { status: 204 });

    await httpInstallationService.update('ins_1', { status: 'suspended' });
    await httpInstallationService.uninstall('ins_1');

    expect(requestOf(fetchMock, 0).init.method).toBe('PATCH');
    expect(requestOf(fetchMock, 1).init.method).toBe('DELETE');
    expect(requestOf(fetchMock, 1).url).toBe('/api/v1/installations/ins_1');
  });

  it('rejects an installation payload that does not match the contract', async () => {
    stubFetch({ body: page([{ ...installation, status: 'exploded' }]) });

    await expect(httpInstallationService.list()).rejects.toMatchObject({
      code: 'invalid_response',
    });
  });
});
