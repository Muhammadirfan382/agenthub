import type { ExecutionListParams, ExecutionService } from '@/services/contracts';
import type { Execution, ExecutionDetail, ID } from '@/types/domain';
import { apiRequest } from './client';
import { orNull } from './orNull';
import { ExecutionDetailSchema, ExecutionSchema, pageSchema } from './schemas';

/** Executions, served by `GET /api/v1/executions`. Nothing runs yet: these are records. */
const PAGE_LIMIT = 200;

const ExecutionPageSchema = pageSchema(ExecutionSchema);

function listQuery(params: ExecutionListParams): string {
  const query = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  const search = params.search?.trim();
  if (search) query.set('search', search);
  if (params.status && params.status !== 'all') query.set('status', params.status);
  if (params.agentId) query.set('agentId', params.agentId);
  return query.toString();
}

export const httpExecutionService: ExecutionService = {
  async list(params: ExecutionListParams = {}): Promise<Execution[]> {
    const page = await apiRequest(`/api/v1/executions?${listQuery(params)}`, ExecutionPageSchema);
    return page.items;
  },

  get(id: ID): Promise<ExecutionDetail | null> {
    return orNull(apiRequest(`/api/v1/executions/${encodeURIComponent(id)}`, ExecutionDetailSchema));
  },
};
