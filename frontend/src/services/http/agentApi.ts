import type { AgentDraft, AgentListParams, AgentService } from '@/services/contracts';
import type { Agent, AgentStatus, Execution, ID } from '@/types/domain';
import { apiRequest, apiRequestVoid } from './client';
import { orNull } from './orNull';
import { AgentSchema, ExecutionSchema, pageSchema } from './schemas';

/**
 * Agents, served by `GET/POST/PUT/PATCH/DELETE /api/v1/agents`.
 *
 * The API pages its collections; the Phase 1 UI filters and sorts a full list
 * in memory. Until the list views are paginated, one page of up to the backend
 * maximum is requested and the total is ignored.
 */
const PAGE_LIMIT = 200;

const AgentPageSchema = pageSchema(AgentSchema);

function listQuery(params: AgentListParams): string {
  const query = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  const search = params.search?.trim();
  if (search) query.set('search', search);
  if (params.status && params.status !== 'all') query.set('status', params.status);
  if (params.risk && params.risk !== 'all') query.set('risk', params.risk);
  if (params.category && params.category !== 'all') query.set('category', params.category);
  if (params.sort) query.set('sort', params.sort);
  return query.toString();
}

export const httpAgentService: AgentService = {
  async list(params: AgentListParams = {}): Promise<Agent[]> {
    const page = await apiRequest(`/api/v1/agents?${listQuery(params)}`, AgentPageSchema);
    return page.items;
  },

  get(id: ID): Promise<Agent | null> {
    return orNull(apiRequest(`/api/v1/agents/${encodeURIComponent(id)}`, AgentSchema));
  },

  create(draft: AgentDraft): Promise<Agent> {
    return apiRequest('/api/v1/agents', AgentSchema, { method: 'POST', body: draft });
  },

  update(id: ID, draft: AgentDraft): Promise<Agent> {
    return apiRequest(`/api/v1/agents/${encodeURIComponent(id)}`, AgentSchema, { method: 'PUT', body: draft });
  },

  remove(id: ID): Promise<void> {
    return apiRequestVoid(`/api/v1/agents/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  setStatus(id: ID, status: AgentStatus): Promise<Agent> {
    return apiRequest(`/api/v1/agents/${encodeURIComponent(id)}/status`, AgentSchema, {
      method: 'PATCH',
      body: { status },
    });
  },

  requestExecution(id: ID): Promise<Execution> {
    return apiRequest(`/api/v1/agents/${encodeURIComponent(id)}/executions`, ExecutionSchema, {
      method: 'POST',
      body: { trigger: 'manual' },
    });
  },
};
