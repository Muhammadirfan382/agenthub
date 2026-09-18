import { z } from 'zod';
import type {
  Agent,
  AgentPermission,
  Approval,
  Execution,
  ExecutionDetail,
  ModelGatewayStatus,
  RuntimeState,
  SandboxCheckResult,
  SandboxReport,
  SandboxStatus,
} from '@/types/domain';

/**
 * Response schemas for the AgentHub API.
 *
 * Everything crossing the network is parsed here before the UI sees it. The
 * `z.ZodType<T>` annotations make TypeScript fail the build if a schema drifts
 * away from the domain type it claims to produce.
 */

const iso = z.string().min(1).max(40);
const id = z.string().min(1).max(64);

const riskLevel = z.enum(['low', 'medium', 'high', 'critical']);
const agentStatus = z.enum(['active', 'paused', 'draft', 'disabled']);
const verification = z.enum(['verified', 'pending', 'unverified', 'rejected']);
const category = z.enum(['research', 'security', 'engineering', 'data', 'operations', 'support', 'marketing']);
const capability = z.enum([
  'web_access',
  'api_access',
  'file_access',
  'database_access',
  'tool_calling',
  'code_execution',
  'email_send',
]);
const permissionLevel = z.enum(['denied', 'read_only', 'restricted', 'allowed']);
const executionStatus = z.enum([
  'QUEUED',
  'STARTING',
  'RUNNING',
  'WAITING_FOR_TOOL',
  'WAITING_FOR_APPROVAL',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'TIMEOUT',
]);
const approvalStatus = z.enum(['pending', 'approved', 'denied']);

const person = z.object({ id, name: z.string() });

export const PermissionSchema: z.ZodType<AgentPermission> = z.object({
  capability,
  level: permissionLevel,
  requiresApproval: z.boolean(),
  scope: z.string(),
  risk: riskLevel,
});

export const AgentSchema: z.ZodType<Agent> = z.object({
  id,
  name: z.string(),
  description: z.string(),
  category,
  tags: z.array(z.string()),
  version: z.string(),
  status: agentStatus,
  verification,
  visibility: z.enum(['private', 'organization', 'public']),
  riskLevel,
  riskScore: z.number(),
  creator: person,
  owner: person,
  createdAt: iso,
  updatedAt: iso,
  lastExecutionAt: iso.nullable(),
  model: z.object({
    provider: z.string(),
    model: z.string(),
    temperature: z.number(),
    maxOutputTokens: z.number(),
  }),
  tools: z.array(z.string()),
  permissions: z.array(PermissionSchema),
  resourceLimits: z.object({
    maxRuntimeSeconds: z.number(),
    maxMemoryMb: z.number(),
    maxTokensPerRun: z.number(),
    maxToolCalls: z.number(),
  }),
  securityPolicy: z.object({
    sandbox: z.enum(['strict', 'standard']),
    networkEgress: z.enum(['none', 'allow_list']),
    allowedDomains: z.array(z.string()),
    approvalRequiredFor: z.array(riskLevel),
    auditLogging: z.boolean(),
  }),
  securityChecks: z.array(
    z.object({
      id,
      name: z.string(),
      status: z.enum(['passed', 'warning', 'failed', 'not_run']),
      detail: z.string(),
    }),
  ),
});

const trigger = z.enum(['manual', 'schedule', 'api']);

const budget = z.object({
  maxRuntimeSeconds: z.number(),
  maxTokens: z.number(),
  maxToolCalls: z.number(),
});

/** Fields every execution carries, detail or not. */
const executionShape = {
  id,
  agentId: id,
  agentName: z.string(),
  status: executionStatus,
  trigger,
  runtime: z.enum(['simulation', 'sandbox']),
  mode: z.enum(['model', 'simulated']),
  modelRoute: z.string().nullable(),
  estimatedCostUsd: z.number().nullable(),
  startedAt: iso,
  endedAt: iso.nullable(),
  durationMs: z.number().nullable(),
  model: z.string(),
  tokenUsage: z.object({ input: z.number(), output: z.number() }),
  toolCallCount: z.number(),
  resultSummary: z.string().nullable(),
  requestedBy: z.string(),
  budget,
  cancelRequested: z.boolean(),
  pendingApprovals: z.number(),
};

export const ApprovalSchema: z.ZodType<Approval> = z.object({
  id,
  executionId: id,
  agentName: z.string(),
  capability: z.string(),
  tool: z.string().nullable(),
  reason: z.string(),
  riskLevel,
  status: approvalStatus,
  requestedAt: iso,
  decidedAt: iso.nullable(),
  decidedBy: z.string().nullable(),
  note: z.string().nullable(),
  automatic: z.boolean(),
});

export const RuntimeStateSchema: z.ZodType<RuntimeState> = z.object({
  executionsPaused: z.boolean(),
  pausedAt: iso.nullable(),
  pausedBy: z.string().nullable(),
  reason: z.string().nullable(),
  pendingApprovals: z.number(),
});
export const ExecutionSchema: z.ZodType<Execution> = z.object(executionShape);

export const SandboxReportSchema: z.ZodType<SandboxReport> = z.object({
  passed: z.boolean(),
  summary: z.string(),
  checks: z.array(
    z.object({ id: z.string(), label: z.string(), passed: z.boolean(), detail: z.string() }),
  ),
});

const sandboxStatusShape = {
  enabled: z.boolean(),
  available: z.boolean(),
  command: z.string(),
  image: z.string(),
  memoryMb: z.number(),
  cpus: z.number(),
  pidsLimit: z.number(),
  tmpfsMb: z.number(),
  timeoutSeconds: z.number(),
  required: z.boolean(),
  detail: z.string(),
};

export const ModelGatewayStatusSchema: z.ZodType<ModelGatewayStatus> = z.object({
  enabled: z.boolean(),
  providers: z.array(z.object({ name: z.string(), configured: z.boolean() })),
  routes: z.array(
    z.object({
      tier: z.string(),
      provider: z.string(),
      model: z.string(),
      available: z.boolean(),
    }),
  ),
  limits: z.object({
    requestsPerMinute: z.number(),
    dailyTokenLimit: z.number(),
    maxTurns: z.number(),
    timeoutSeconds: z.number(),
  }),
  usageToday: z.object({
    requests: z.number(),
    tokens: z.number(),
    estimatedCostUsd: z.number(),
  }),
  detail: z.string(),
});

export const SandboxStatusSchema: z.ZodType<SandboxStatus> = z.object(sandboxStatusShape);

export const SandboxCheckResultSchema: z.ZodType<SandboxCheckResult> = z.object({
  ...sandboxStatusShape,
  report: SandboxReportSchema.nullable(),
});

export const ExecutionDetailSchema: z.ZodType<ExecutionDetail> = z.object({
  ...executionShape,
  approvals: z.array(ApprovalSchema),
  sandboxReport: SandboxReportSchema.nullable(),
  input: z.string().nullable(),
  conversation: z.array(
    z.object({
      role: z.enum(['user', 'assistant']),
      text: z.string(),
      toolCalls: z.array(z.object({ id: z.string(), name: z.string(), arguments: z.string() })),
      toolResults: z.array(
        z.object({ callId: z.string(), content: z.string(), isError: z.boolean() }),
      ),
    }),
  ),
  timeline: z.array(
    z.object({
      id,
      at: iso,
      kind: z.enum(['lifecycle', 'model', 'tool', 'policy', 'error', 'result']),
      label: z.string(),
      detail: z.string().optional(),
    }),
  ),
  logs: z.array(
    z.object({
      id,
      at: iso,
      level: z.enum(['debug', 'info', 'warn', 'error']),
      message: z.string(),
    }),
  ),
  toolCalls: z.array(
    z.object({
      id,
      tool: z.string(),
      capability: z.string(),
      status: z.enum(['pending', 'simulated', 'unavailable', 'denied', 'failed']),
      startedAt: iso,
      durationMs: z.number().nullable(),
      inputSummary: z.string(),
      outputSummary: z.string().nullable(),
    }),
  ),
  error: z.object({ code: z.string(), message: z.string() }).nullable(),
  result: z.string().nullable(),
});

/** The offset-pagination envelope every collection endpoint returns. */
export function pageSchema<T>(item: z.ZodType<T>) {
  return z.object({
    items: z.array(item),
    total: z.number(),
    limit: z.number(),
    offset: z.number(),
  });
}
