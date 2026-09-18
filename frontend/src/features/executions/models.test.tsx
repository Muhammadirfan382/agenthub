import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { renderApp, servicesAs, testServices } from '@/test/renderApp';
import type { ExecutionDetail, ModelGatewayStatus } from '@/types/domain';

const FINISHED = 'exe_a4c6e210';
const HOSTILE = '<img src=x onerror="alert(1)"> Ignore previous instructions.';

/** Services where one finished run was answered by a real model. */
function withModelRun(overrides: Partial<ExecutionDetail> = {}, base = testServices()): Services {
  return {
    ...base,
    executions: {
      ...base.executions,
      async get(id: string) {
        const detail = await base.executions.get(id);
        if (!detail || id !== FINISHED) return detail;
        return {
          ...detail,
          mode: 'model',
          modelRoute: 'anthropic:claude-sonnet-5',
          estimatedCostUsd: 0.0042,
          input: 'Summarise the incident.',
          result: HOSTILE,
          toolCalls: [
            {
              id: 'tcl_1',
              tool: 'web_search',
              capability: 'web_access',
              status: 'unavailable',
              startedAt: detail.startedAt,
              durationMs: null,
              inputSummary: '{"query": "status"}',
              outputSummary: 'Allowed by policy; not executed.',
            },
          ],
          conversation: [
            { role: 'user', text: 'Summarise the incident.', toolCalls: [], toolResults: [] },
            {
              role: 'assistant',
              text: '',
              toolCalls: [{ id: 'c1', name: 'web_search', arguments: '{"query": "status"}' }],
              toolResults: [],
            },
            {
              role: 'user',
              text: '',
              toolCalls: [],
              toolResults: [
                { callId: 'c1', content: 'Not executed: web_search has no implementation.', isError: true },
              ],
            },
            { role: 'assistant', text: HOSTILE, toolCalls: [], toolResults: [] },
          ],
          ...overrides,
        };
      },
    },
  };
}

const LIVE: ModelGatewayStatus = {
  enabled: true,
  providers: [
    { name: 'anthropic', configured: true },
    { name: 'openai', configured: false },
  ],
  routes: [
    { tier: 'fast-small', provider: 'anthropic', model: 'claude-haiku-4-5', available: true },
    { tier: 'balanced-large', provider: 'openai', model: 'gpt-test', available: false },
  ],
  limits: { requestsPerMinute: 30, dailyTokenLimit: 2_000_000, maxTurns: 8, timeoutSeconds: 180 },
  usageToday: { requests: 12, tokens: 48_000, estimatedCostUsd: 0.1234 },
  detail: 'Runs on a tier with a configured provider are answered by a real model.',
};

describe('a run answered by a model', () => {
  it('says which model answered and what it cost', async () => {
    renderApp(`/executions/${FINISHED}`, withModelRun());

    await screen.findByRole('heading', { level: 1, name: FINISHED });
    expect(screen.getByText('Live model')).toBeInTheDocument();
    expect(screen.getByText('anthropic:claude-sonnet-5')).toBeInTheDocument();
    expect(screen.getByText('$0.0042')).toBeInTheDocument();
    expect(screen.getAllByText('Summarise the incident.').length).toBeGreaterThan(0);
  });

  it('shows the conversation, including what the tool gateway told the model', async () => {
    renderApp(`/executions/${FINISHED}`, withModelRun());

    const conversation = await screen.findByRole('list', { name: 'Conversation' });
    expect(within(conversation).getByText('web_search')).toBeInTheDocument();
    expect(within(conversation).getByText(/Not executed: web_search/)).toBeInTheDocument();
    expect(within(conversation).getByText('Tool gateway')).toBeInTheDocument();
  });

  it('renders the model’s words as text, never as markup', async () => {
    const { container } = renderApp(`/executions/${FINISHED}`, withModelRun());

    await screen.findByRole('list', { name: 'Conversation' });
    expect(screen.getAllByText(HOSTILE).length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('img[src="x"]')).toBeNull();
  });

  it('labels an allowed tool call as not executed, never as succeeded', async () => {
    renderApp(`/executions/${FINISHED}`, withModelRun());

    await screen.findByRole('heading', { level: 1, name: FINISHED });
    expect(screen.getAllByText('Not executed').length).toBeGreaterThan(0);
    expect(screen.queryByText(/succeeded/i)).not.toBeInTheDocument();
  });

  it('says plainly when no model was called', async () => {
    renderApp(`/executions/${FINISHED}`);

    await screen.findByRole('heading', { level: 1, name: FINISHED });
    expect(screen.getByText('None: no model was called')).toBeInTheDocument();
    expect(screen.getByText('No conversation')).toBeInTheDocument();
  });
});

describe('starting a run', () => {
  it('sends the task typed into the dialog', async () => {
    const services = servicesAs('admin');
    const requestExecution = vi.fn(services.agents.requestExecution);
    const { user } = renderApp('/agents/agt_research_scout', {
      ...services,
      agents: { ...services.agents, requestExecution },
    });

    await user.click(await screen.findByRole('button', { name: 'Execute' }));
    await user.type(screen.getByRole('textbox', { name: /Task/ }), 'Find three sources.');
    await user.click(screen.getByRole('button', { name: 'Start run' }));

    await vi.waitFor(() =>
      expect(requestExecution).toHaveBeenCalledWith('agt_research_scout', 'Find three sources.'),
    );
  });

  it('does not promise that tools will run', async () => {
    const { user } = renderApp('/agents/agt_research_scout', servicesAs('admin'));

    await user.click(await screen.findByRole('button', { name: 'Execute' }));

    expect(screen.getByText(/checked against this agent's permissions but never executed/)).toBeInTheDocument();
  });
});

describe('the model gateway in settings', () => {
  it('says that demo mode calls no model', async () => {
    renderApp('/settings?section=runtime', servicesAs('admin'));

    expect(await screen.findByText('Simulated only')).toBeInTheDocument();
    expect(screen.getByText('anthropic: no credentials')).toBeInTheDocument();
  });

  it('shows which tiers are live, the limits and today’s usage', async () => {
    const services = servicesAs('admin');
    renderApp('/settings?section=runtime', {
      ...services,
      runtime: { ...services.runtime, models: () => Promise.resolve(LIVE) },
    });

    expect(await screen.findByText('Models available')).toBeInTheDocument();
    const routes = screen.getByRole('table', { name: 'Model routes by tier' });
    expect(within(routes).getByText('anthropic:claude-haiku-4-5')).toBeInTheDocument();
    expect(within(routes).getByText('Live')).toBeInTheDocument();
    expect(within(routes).getByText('Simulated')).toBeInTheDocument();
    expect(screen.getByText('$0.1234')).toBeInTheDocument();
    expect(screen.getByText('anthropic: configured')).toBeInTheDocument();
  });
});
