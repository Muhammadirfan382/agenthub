import { z } from 'zod';
import { CAPABILITY_KEYS, CAPABILITY_META } from '@/components/status/meta';
import { RISK_RANK } from '@/lib/risk';
import type { AgentDraft } from '@/services/contracts';
import type { Agent, AgentCategory, CapabilityKey, PermissionLevel, RiskLevel } from '@/types/domain';
import { AGENT_CATEGORIES, RISK_LEVELS } from '@/types/domain';

export const MODEL_OPTIONS = [
  { value: 'fast-small', label: 'Fast (small)' },
  { value: 'balanced-large', label: 'Balanced (large)' },
  { value: 'reasoning-large', label: 'Reasoning (large)' },
] as const;

export const TOOL_OPTIONS: { id: string; label: string; capability: CapabilityKey }[] = [
  { id: 'web_search', label: 'Web search', capability: 'web_access' },
  { id: 'document_reader', label: 'Document reader', capability: 'file_access' },
  { id: 'sql_readonly', label: 'SQL query (read only)', capability: 'database_access' },
  { id: 'api_request', label: 'HTTP API request', capability: 'api_access' },
  { id: 'code_sandbox', label: 'Code sandbox', capability: 'code_execution' },
  { id: 'email_draft', label: 'Email sender', capability: 'email_send' },
  { id: 'chart_renderer', label: 'Chart renderer', capability: 'tool_calling' },
];

/** Inherent risk of each capability before the access level is considered. */
export const CAPABILITY_BASE_RISK: Record<CapabilityKey, RiskLevel> = {
  web_access: 'medium',
  api_access: 'high',
  file_access: 'medium',
  database_access: 'high',
  tool_calling: 'low',
  code_execution: 'critical',
  email_send: 'high',
};

export function permissionRisk(capability: CapabilityKey, level: PermissionLevel): RiskLevel {
  const base = RISK_RANK[CAPABILITY_BASE_RISK[capability]];
  const adjusted = level === 'read_only' ? base - 1 : level === 'allowed' ? base + 1 : base;
  return RISK_LEVELS[Math.max(0, Math.min(3, adjusted))] ?? 'low';
}

const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/;
const TAG = /^[a-z0-9][a-z0-9-]{0,23}$/;
const HOSTNAME = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;

const intInRange = (label: string, min: number, max: number) =>
  z
    .number({ error: `Enter a number for ${label}.` })
    .int(`${label} must be a whole number.`)
    .min(min, `${label} must be at least ${min}.`)
    .max(max, `${label} must be at most ${max}.`);

const permissionSchema = z.object({
  capability: z.enum(CAPABILITY_KEYS as [CapabilityKey, ...CapabilityKey[]]),
  level: z.enum(['denied', 'read_only', 'restricted', 'allowed']),
  requiresApproval: z.boolean(),
  scope: z.string().trim().max(120, 'Scope must be 120 characters or fewer.'),
});

export const agentFormSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(3, 'Name must be at least 3 characters.')
      .max(60, 'Name must be 60 characters or fewer.')
      .regex(/^[A-Za-z0-9][A-Za-z0-9 ._-]*$/, 'Use letters, numbers, spaces, dots, dashes or underscores.'),
    version: z.string().trim().regex(SEMVER, 'Use semantic versioning, for example 1.0.0.'),
    description: z
      .string()
      .trim()
      .min(20, 'Description must be at least 20 characters.')
      .max(500, 'Description must be 500 characters or fewer.'),
    category: z.string().refine((value) => (AGENT_CATEGORIES as readonly string[]).includes(value), 'Choose a category.'),
    tags: z
      .array(z.string().regex(TAG, 'Tags use lowercase letters, numbers and dashes (max 24 characters).'))
      .min(1, 'Add at least one tag.')
      .max(10, 'Use at most 10 tags.')
      .refine((tags) => new Set(tags).size === tags.length, 'Tags must be unique.'),
    model: z.object({
      model: z.string().refine((value) => MODEL_OPTIONS.some((m) => m.value === value), 'Choose a model.'),
      temperature: z
        .number({ error: 'Enter a number for temperature.' })
        .min(0, 'Temperature must be between 0 and 2.')
        .max(2, 'Temperature must be between 0 and 2.'),
      maxOutputTokens: intInRange('Max output tokens', 256, 32000),
    }),
    tools: z.array(z.string()).max(10, 'Select at most 10 tools.'),
    permissions: z.array(permissionSchema).length(CAPABILITY_KEYS.length),
    resourceLimits: z.object({
      maxRuntimeSeconds: intInRange('Max runtime', 10, 3600),
      maxMemoryMb: intInRange('Max memory', 128, 8192),
      maxTokensPerRun: intInRange('Max tokens per run', 1000, 200000),
      maxToolCalls: intInRange('Max tool calls', 0, 500),
    }),
    securityPolicy: z.object({
      sandbox: z.enum(['strict', 'standard']),
      networkEgress: z.enum(['none', 'allow_list']),
      allowedDomainsText: z.string().max(2000, 'Too many domains.'),
      approvalRequiredFor: z.array(z.enum(RISK_LEVELS as [RiskLevel, ...RiskLevel[]])),
      auditLogging: z.boolean(),
    }),
  })
  .superRefine((values, ctx) => {
    const levelOf = (capability: CapabilityKey) =>
      values.permissions.find((p) => p.capability === capability)?.level ?? 'denied';

    // Selected tools must have the capability they need.
    for (const toolId of values.tools) {
      const tool = TOOL_OPTIONS.find((t) => t.id === toolId);
      if (tool && levelOf(tool.capability) === 'denied') {
        ctx.addIssue({
          code: 'custom',
          path: ['tools'],
          message: `"${tool.label}" needs ${CAPABILITY_META[tool.capability].label}, which is denied in Permissions.`,
        });
      }
    }

    values.permissions.forEach((permission, index) => {
      if (permission.level === 'denied') return;
      if (permission.scope.length < 3) {
        ctx.addIssue({ code: 'custom', path: ['permissions', index, 'scope'], message: 'Describe the scope of this permission.' });
      }
      if (permissionRisk(permission.capability, permission.level) === 'critical' && !permission.requiresApproval) {
        ctx.addIssue({
          code: 'custom',
          path: ['permissions', index, 'requiresApproval'],
          message: 'Critical-risk capabilities must require human approval.',
        });
      }
    });

    if (levelOf('code_execution') !== 'denied' && values.securityPolicy.sandbox !== 'strict') {
      ctx.addIssue({ code: 'custom', path: ['securityPolicy', 'sandbox'], message: 'Code execution requires the strict sandbox.' });
    }

    const domains = parseDomains(values.securityPolicy.allowedDomainsText);
    if (values.securityPolicy.networkEgress === 'allow_list') {
      if (domains.length === 0) {
        ctx.addIssue({ code: 'custom', path: ['securityPolicy', 'allowedDomainsText'], message: 'Add at least one allowed domain, or set egress to none.' });
      }
      const invalid = domains.find((d) => !HOSTNAME.test(d));
      if (invalid) {
        ctx.addIssue({
          code: 'custom',
          path: ['securityPolicy', 'allowedDomainsText'],
          message: `"${invalid}" is not a valid domain. Use hostnames only, without a scheme, path or wildcard.`,
        });
      }
    } else if (levelOf('web_access') !== 'denied' || levelOf('api_access') !== 'denied') {
      ctx.addIssue({
        code: 'custom',
        path: ['securityPolicy', 'networkEgress'],
        message: 'Web or API access needs an egress allow-list.',
      });
    }

    const grantsHighRisk = values.permissions.some(
      (p) => p.level !== 'denied' && RISK_RANK[permissionRisk(p.capability, p.level)] >= RISK_RANK.high,
    );
    if (grantsHighRisk && !values.securityPolicy.auditLogging) {
      ctx.addIssue({ code: 'custom', path: ['securityPolicy', 'auditLogging'], message: 'Audit logging is required when high-risk capabilities are granted.' });
    }

    if (values.tools.length > 0 && values.resourceLimits.maxToolCalls === 0) {
      ctx.addIssue({ code: 'custom', path: ['resourceLimits', 'maxToolCalls'], message: 'Allow at least one tool call when tools are selected.' });
    }

    if (values.resourceLimits.maxTokensPerRun < values.model.maxOutputTokens) {
      ctx.addIssue({
        code: 'custom',
        path: ['resourceLimits', 'maxTokensPerRun'],
        message: 'Max tokens per run must be at least the model’s max output tokens.',
      });
    }
  });

export type AgentFormInput = z.input<typeof agentFormSchema>;
export type AgentFormValues = z.output<typeof agentFormSchema>;

export function parseDomains(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((d) => d.trim().toLowerCase())
    .filter(Boolean);
}

export const defaultAgentFormValues: AgentFormInput = {
  name: '',
  version: '0.1.0',
  description: '',
  category: '',
  tags: [],
  model: { model: 'balanced-large', temperature: 0.2, maxOutputTokens: 4096 },
  tools: [],
  permissions: CAPABILITY_KEYS.map((capability) => ({ capability, level: 'denied', requiresApproval: false, scope: '' })),
  resourceLimits: { maxRuntimeSeconds: 300, maxMemoryMb: 512, maxTokensPerRun: 50000, maxToolCalls: 20 },
  securityPolicy: { sandbox: 'strict', networkEgress: 'none', allowedDomainsText: '', approvalRequiredFor: ['high', 'critical'], auditLogging: true },
};

export function toAgentDraft(values: AgentFormValues): AgentDraft {
  return {
    name: values.name,
    description: values.description,
    category: values.category as AgentCategory,
    tags: values.tags,
    version: values.version,
    model: { provider: 'Model gateway', model: values.model.model, temperature: values.model.temperature, maxOutputTokens: values.model.maxOutputTokens },
    tools: values.tools,
    permissions: values.permissions.map((p) => ({
      capability: p.capability,
      level: p.level,
      requiresApproval: p.level === 'denied' ? false : p.requiresApproval,
      scope: p.level === 'denied' ? 'Not granted' : p.scope,
      risk: permissionRisk(p.capability, p.level),
    })),
    resourceLimits: values.resourceLimits,
    securityPolicy: {
      sandbox: values.securityPolicy.sandbox,
      networkEgress: values.securityPolicy.networkEgress,
      allowedDomains: values.securityPolicy.networkEgress === 'allow_list' ? parseDomains(values.securityPolicy.allowedDomainsText) : [],
      approvalRequiredFor: values.securityPolicy.approvalRequiredFor,
      auditLogging: values.securityPolicy.auditLogging,
    },
  };
}

export function agentToFormValues(agent: Agent): AgentFormInput {
  return {
    name: agent.name,
    version: agent.version,
    description: agent.description,
    category: agent.category,
    tags: agent.tags,
    model: { model: agent.model.model, temperature: agent.model.temperature, maxOutputTokens: agent.model.maxOutputTokens },
    tools: agent.tools.filter((tool) => TOOL_OPTIONS.some((option) => option.id === tool)),
    permissions: CAPABILITY_KEYS.map((capability) => {
      const existing = agent.permissions.find((p) => p.capability === capability);
      return {
        capability,
        level: existing?.level ?? 'denied',
        requiresApproval: existing?.requiresApproval ?? false,
        scope: existing && existing.level !== 'denied' ? existing.scope : '',
      };
    }),
    resourceLimits: agent.resourceLimits,
    securityPolicy: {
      sandbox: agent.securityPolicy.sandbox,
      networkEgress: agent.securityPolicy.networkEgress,
      allowedDomainsText: agent.securityPolicy.allowedDomains.join('\n'),
      approvalRequiredFor: agent.securityPolicy.approvalRequiredFor,
      auditLogging: agent.securityPolicy.auditLogging,
    },
  };
}
