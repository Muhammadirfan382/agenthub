import { z } from 'zod';
import type { ExecutionListParams, ExecutionService, RuntimeService } from '@/services/contracts';
import type {
  Approval,
  ApprovalDecision,
  Execution,
  ExecutionDetail,
  ID,
  RuntimeState,
  SandboxCheckResult,
  SandboxStatus,
} from '@/types/domain';
import { apiRequest } from './client';
import { orNull } from './orNull';
import {
  ApprovalSchema,
  ExecutionDetailSchema,
  ExecutionSchema,
  RuntimeStateSchema,
  SandboxCheckResultSchema,
  SandboxStatusSchema,
  pageSchema,
} from './schemas';

/** Executions, served by `GET /api/v1/executions`, and the controls over them. */
const PAGE_LIMIT = 200;

const ExecutionPageSchema = pageSchema(ExecutionSchema);
const ApprovalPageSchema = pageSchema(ApprovalSchema);

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

  cancel(id: ID): Promise<ExecutionDetail> {
    return apiRequest(
      `/api/v1/executions/${encodeURIComponent(id)}/cancel`,
      ExecutionDetailSchema,
      { method: 'POST' },
    );
  },

  async pendingApprovals(): Promise<Approval[]> {
    const page = await apiRequest(
      `/api/v1/executions/approvals?limit=${PAGE_LIMIT}`,
      ApprovalPageSchema,
    );
    return page.items;
  },

  decideApproval(
    executionId: ID,
    approvalId: ID,
    decision: ApprovalDecision,
    note?: string,
  ): Promise<ExecutionDetail> {
    return apiRequest(
      `/api/v1/executions/${encodeURIComponent(executionId)}/approvals/${encodeURIComponent(approvalId)}`,
      ExecutionDetailSchema,
      { method: 'POST', body: { decision, note: note ?? null } },
    );
  },
};

export const httpRuntimeService: RuntimeService = {
  state(): Promise<RuntimeState> {
    return apiRequest('/api/v1/organization/runtime', RuntimeStateSchema);
  },

  setExecutionsPaused(paused: boolean, reason?: string): Promise<RuntimeState> {
    return apiRequest('/api/v1/organization/runtime', RuntimeStateSchema, {
      method: 'PATCH',
      body: { executionsPaused: paused, reason: reason ?? null },
    });
  },

  sandbox(): Promise<SandboxStatus> {
    return apiRequest('/api/v1/organization/sandbox', SandboxStatusSchema);
  },

  checkSandbox(): Promise<SandboxCheckResult> {
    return apiRequest('/api/v1/organization/sandbox/check', SandboxCheckResultSchema, {
      method: 'POST',
    });
  },
};

/** The stream URL for `EventSource`; cookies authenticate it, same-origin. */
export function executionStreamUrl(id: ID, baseUrl: string): string {
  return `${baseUrl}/api/v1/executions/${encodeURIComponent(id)}/stream`;
}

export const StreamStatusSchema = z.object({ status: z.string() });
