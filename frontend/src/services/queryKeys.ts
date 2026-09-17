import type { AgentListParams, ExecutionListParams, MarketplaceParams } from './contracts';

/** Centralised TanStack Query keys, so invalidation stays consistent. */
export const queryKeys = {
  agents: {
    all: ['agents'] as const,
    list: (params: AgentListParams) => ['agents', 'list', params] as const,
    detail: (id: string) => ['agents', 'detail', id] as const,
  },
  marketplace: {
    all: ['marketplace'] as const,
    list: (params: MarketplaceParams) => ['marketplace', 'list', params] as const,
    detail: (id: string) => ['marketplace', 'detail', id] as const,
    tags: ['marketplace', 'tags'] as const,
  },
  installations: {
    all: ['installations'] as const,
    list: ['installations', 'list'] as const,
    detail: (id: string) => ['installations', 'detail', id] as const,
  },
  versions: {
    all: ['versions'] as const,
    list: (agentId: string) => ['versions', 'list', agentId] as const,
  },
  executions: {
    all: ['executions'] as const,
    list: (params: ExecutionListParams) => ['executions', 'list', params] as const,
    detail: (id: string) => ['executions', 'detail', id] as const,
    approvals: ['executions', 'approvals'] as const,
  },
  runtime: {
    all: ['runtime'] as const,
    state: ['runtime', 'state'] as const,
  },
  security: {
    overview: ['security', 'overview'] as const,
    events: ['security', 'events'] as const,
    policies: ['security', 'policies'] as const,
  },
  system: {
    summary: ['system', 'summary'] as const,
    components: ['system', 'components'] as const,
    backendHealth: ['system', 'backend-health'] as const,
  },
  analytics: {
    summary: ['analytics', 'summary'] as const,
  },
  auth: {
    session: ['auth', 'session'] as const,
  },
  members: {
    all: ['members'] as const,
    list: ['members', 'list'] as const,
  },
};
