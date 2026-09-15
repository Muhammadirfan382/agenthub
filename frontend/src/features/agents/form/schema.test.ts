import { describe, expect, it } from 'vitest';
import { type AgentFormInput, agentFormSchema, defaultAgentFormValues, permissionRisk, toAgentDraft } from './schema';

function valid(overrides: Partial<AgentFormInput> = {}): AgentFormInput {
  return {
    ...structuredClone(defaultAgentFormValues),
    name: 'Test Agent',
    description: 'A sufficiently long description for validation.',
    category: 'research',
    tags: ['test'],
    ...overrides,
  };
}

function messages(input: AgentFormInput): string[] {
  const result = agentFormSchema.safeParse(input);
  return result.success ? [] : result.error.issues.map((issue) => issue.message);
}

function withPermission(input: AgentFormInput, capability: string, patch: Partial<AgentFormInput['permissions'][number]>) {
  return { ...input, permissions: input.permissions.map((p) => (p.capability === capability ? { ...p, ...patch } : p)) };
}

describe('agent form schema', () => {
  it('accepts a minimal deny-by-default configuration', () => {
    expect(messages(valid())).toEqual([]);
  });

  it('rejects duplicate and malformed tags', () => {
    expect(messages(valid({ tags: ['dup', 'dup'] }))).toContain('Tags must be unique.');
    expect(messages(valid({ tags: ['Has Spaces'] }))).toContain('Tags use lowercase letters, numbers and dashes (max 24 characters).');
  });

  it('requires approval for critical-risk capabilities', () => {
    const input = withPermission(valid(), 'code_execution', { level: 'restricted', scope: 'Sandboxed tests', requiresApproval: false });
    expect(messages(input)).toContain('Critical-risk capabilities must require human approval.');
  });

  it('requires the strict sandbox for code execution', () => {
    const base = withPermission(valid(), 'code_execution', { level: 'restricted', scope: 'Sandboxed tests', requiresApproval: true });
    const input = { ...base, securityPolicy: { ...base.securityPolicy, sandbox: 'standard' as const } };
    expect(messages(input)).toContain('Code execution requires the strict sandbox.');
  });

  it('requires a valid egress allow-list for web access', () => {
    const web = withPermission(valid(), 'web_access', { level: 'restricted', scope: 'Docs only' });
    expect(messages(web)).toContain('Web or API access needs an egress allow-list.');

    const noDomains = { ...web, securityPolicy: { ...web.securityPolicy, networkEgress: 'allow_list' as const, allowedDomainsText: '' } };
    expect(messages(noDomains)).toContain('Add at least one allowed domain, or set egress to none.');

    const wildcard = { ...noDomains, securityPolicy: { ...noDomains.securityPolicy, allowedDomainsText: 'https://*.example.com' } };
    expect(messages(wildcard).some((m) => m.includes('is not a valid domain'))).toBe(true);

    const ok = { ...noDomains, securityPolicy: { ...noDomains.securityPolicy, allowedDomainsText: 'docs.example.com' } };
    expect(messages(ok)).toEqual([]);
  });

  it('rejects inconsistent resource limits', () => {
    const input = valid({ resourceLimits: { maxRuntimeSeconds: 300, maxMemoryMb: 512, maxTokensPerRun: 2000, maxToolCalls: 20 } });
    expect(messages(input)).toContain('Max tokens per run must be at least the model’s max output tokens.');
  });

  it('derives permission risk from capability and access level', () => {
    expect(permissionRisk('code_execution', 'restricted')).toBe('critical');
    expect(permissionRisk('web_access', 'read_only')).toBe('low');
    expect(permissionRisk('api_access', 'allowed')).toBe('critical');
  });

  it('maps form values to a typed service draft', () => {
    const parsed = agentFormSchema.parse(valid());
    const draft = toAgentDraft(parsed);
    expect(draft.permissions.every((p) => p.level === 'denied' && p.scope === 'Not granted')).toBe(true);
    expect(draft.securityPolicy.allowedDomains).toEqual([]);
  });
});
