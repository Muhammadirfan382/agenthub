import { z } from 'zod';
import type { Agent, AgentPermission, Execution, ExecutionDetail } from '@/types/domain';

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
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'TIMEOUT',
]);
const trigger = z.enum(['manual', 'schedule', 'api']);

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
  versions: z.array(
    z.object({
      version: z.string(),
      releasedAt: iso,
      status: z.enum(['current', 'previous', 'deprecated', 'draft']),
      changes: z.array(z.string()),
    }),
  ),
  securityChecks: z.array(
    z.object({
      id,
      name: z.string(),
      status: z.enum(['passed', 'warning', 'failed', 'not_run']),
      detail: z.string(),
    }),
  ),
});

export const ExecutionSchema: z.ZodType<Execution> = z.object({
  id,
  agentId: id,
  agentName: z.string(),
  status: executionStatus,
  trigger,
  startedAt: iso,
  endedAt: iso.nullable(),
  durationMs: z.number().nullable(),
  model: z.string(),
  tokenUsage: z.object({ input: z.number(), output: z.number() }),
  toolCallCount: z.number(),
  resultSummary: z.string().nullable(),
});

export const ExecutionDetailSchema: z.ZodType<ExecutionDetail> = z.object({
  id,
  agentId: id,
  agentName: z.string(),
  status: executionStatus,
  trigger,
  startedAt: iso,
  endedAt: iso.nullable(),
  durationMs: z.number().nullable(),
  model: z.string(),
  tokenUsage: z.object({ input: z.number(), output: z.number() }),
  toolCallCount: z.number(),
  resultSummary: z.string().nullable(),
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
      status: z.enum(['succeeded', 'failed', 'denied', 'pending']),
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
