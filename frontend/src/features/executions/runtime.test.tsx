import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { renderApp, servicesAs, testServices } from '@/test/renderApp';
import type { Approval, ExecutionDetail } from '@/types/domain';

const RUNNING = 'exe_7f3a91c2';

function approval(overrides: Partial<Approval> = {}): Approval {
  return {
    id: 'apr_1',
    executionId: RUNNING,
    agentName: 'Threat Triage',
    capability: 'api_access',
    tool: 'api_request',
    reason: 'api_request uses api_access (restricted), which needs a person to approve.',
    riskLevel: 'high',
    status: 'pending',
    requestedAt: '2026-09-17T09:00:00.000Z',
    decidedAt: null,
    decidedBy: null,
    note: null,
    automatic: false,
    ...overrides,
  };
}

/** Demo services whose running execution is paused waiting for approval. */
function servicesWithApproval(
  base: Services = testServices(),
  pending: Approval = approval(),
): Services {
  return {
    ...base,
    executions: {
      ...base.executions,
      async get(id: string) {
        const detail = await base.executions.get(id);
        if (!detail || id !== RUNNING) return detail;
        const paused: ExecutionDetail = {
          ...detail,
          status: 'WAITING_FOR_APPROVAL',
          pendingApprovals: 1,
          approvals: [pending],
        };
        return paused;
      },
      pendingApprovals: () => Promise.resolve([pending]),
    },
  };
}

describe('controlling a run', () => {
  it('offers to cancel a run that has not finished', async () => {
    const services = testServices();
    const cancel = vi.fn(services.executions.cancel);
    const { user } = renderApp(`/executions/${RUNNING}`, {
      ...services,
      executions: { ...services.executions, cancel },
    });

    await screen.findByRole('heading', { level: 1, name: RUNNING });
    await user.click(screen.getByRole('button', { name: 'Cancel run' }));
    await user.click(await screen.findByRole('button', { name: 'Stop the run' }));

    expect(cancel).toHaveBeenCalledWith(RUNNING);
  });

  it('does not offer cancellation once a run has finished', async () => {
    renderApp('/executions/exe_a4c6e210');

    await screen.findByRole('heading', { level: 1, name: 'exe_a4c6e210' });
    expect(screen.queryByRole('button', { name: 'Cancel run' })).not.toBeInTheDocument();
  });

  it('says plainly that nothing was executed', async () => {
    renderApp(`/executions/${RUNNING}`);

    await screen.findByRole('heading', { level: 1, name: RUNNING });
    expect(screen.getByText(/Budget/)).toBeInTheDocument();
    expect(screen.getByText(/900s ·/)).toBeInTheDocument();
  });
});

describe('approvals', () => {
  it('shows what is waiting and who asked for it', async () => {
    renderApp(`/executions/${RUNNING}`, servicesWithApproval());

    expect(await screen.findByText('Approvals')).toBeInTheDocument();
    expect(screen.getByText('api_request · API access')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Refuse' })).toBeEnabled();
  });

  it('sends the decision and the note', async () => {
    const base = testServices();
    const decideApproval = vi.fn(base.executions.decideApproval);
    const services = servicesWithApproval({
      ...base,
      executions: { ...base.executions, decideApproval },
    });

    const { user } = renderApp(`/executions/${RUNNING}`, services);

    await screen.findByText('Approvals');
    await user.type(screen.getByRole('textbox', { name: /Note for api_request/ }), 'Scope is fine');
    await user.click(screen.getByRole('button', { name: 'Approve' }));

    expect(decideApproval).toHaveBeenCalledWith(RUNNING, 'apr_1', 'approved', 'Scope is fine');
  });

  it('refusing is a normal outcome, not an error', async () => {
    const base = testServices();
    const decideApproval = vi.fn(base.executions.decideApproval);
    const services = servicesWithApproval({
      ...base,
      executions: { ...base.executions, decideApproval },
    });

    const { user } = renderApp(`/executions/${RUNNING}`, services);

    await screen.findByText('Approvals');
    await user.click(screen.getByRole('button', { name: 'Refuse' }));

    expect(decideApproval).toHaveBeenCalledWith(RUNNING, 'apr_1', 'denied', undefined);
  });

  it('a viewer can see the request but not decide it', async () => {
    renderApp(`/executions/${RUNNING}`, servicesWithApproval(servicesAs('viewer')));

    await screen.findByText('Approvals');
    expect(screen.getByText('Your role cannot decide these')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled();
  });

  it('surfaces waiting approvals on the executions page', async () => {
    renderApp('/executions', servicesWithApproval());

    expect(await screen.findByText('1 step is waiting for approval')).toBeInTheDocument();
    expect(screen.getAllByText('Threat Triage').length).toBeGreaterThan(0);
  });
});

describe('the kill switch', () => {
  it('stops every execution when an administrator engages it', async () => {
    const services = servicesAs('admin');
    const setExecutionsPaused = vi.fn(services.runtime.setExecutionsPaused);
    const { user } = renderApp('/settings?section=runtime', {
      ...services,
      runtime: { ...services.runtime, setExecutionsPaused },
    });

    await screen.findByText('Execution kill switch');
    await user.type(
      screen.getByRole('textbox', { name: /Reason/ }),
      'Investigating tool activity',
    );
    await user.click(screen.getByRole('button', { name: 'Stop all executions' }));
    await user.click(await screen.findByRole('button', { name: 'Stop executions' }));

    expect(setExecutionsPaused).toHaveBeenCalledWith(true, 'Investigating tool activity');
  });

  it('will not let a member engage it', async () => {
    renderApp('/settings?section=runtime', servicesAs('member'));

    await screen.findByText('Execution kill switch');
    expect(screen.getByText('Your role cannot stop executions')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stop all executions' })).toBeDisabled();
  });

  it('only the owner may release it', async () => {
    const services = servicesAs('admin');
    const paused = {
      executionsPaused: true,
      pausedAt: '2026-09-17T09:00:00.000Z',
      pausedBy: 'Test Person',
      reason: 'Incident 42',
      pendingApprovals: 0,
    };

    renderApp('/settings?section=runtime', {
      ...services,
      runtime: { ...services.runtime, state: () => Promise.resolve(paused) },
    });

    await screen.findByText('Execution kill switch');
    expect(screen.getByText('Only the owner can release this')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume executions' })).toBeDisabled();
  });

  it('warns everywhere while executions are stopped', async () => {
    const services = testServices();
    const paused = {
      executionsPaused: true,
      pausedAt: '2026-09-17T09:00:00.000Z',
      pausedBy: 'Test Person',
      reason: 'Incident 42',
      pendingApprovals: 0,
    };

    renderApp('/executions', {
      ...services,
      runtime: { ...services.runtime, state: () => Promise.resolve(paused) },
    });

    expect(
      await screen.findByText('Executions are stopped for this organization'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Incident 42/)).toBeInTheDocument();
  });
});
