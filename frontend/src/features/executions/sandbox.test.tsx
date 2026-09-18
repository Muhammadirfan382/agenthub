import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { renderApp, servicesAs, testServices } from '@/test/renderApp';
import type { ExecutionDetail, SandboxReport, SandboxStatus } from '@/types/domain';

const FINISHED = 'exe_a4c6e210';

const AVAILABLE: SandboxStatus = {
  enabled: true,
  available: true,
  command: 'docker',
  image: 'agenthub/sandbox:0.6.0',
  memoryMb: 512,
  cpus: 1,
  pidsLimit: 128,
  tmpfsMb: 64,
  timeoutSeconds: 60,
  required: false,
  detail: 'A container runtime is available.',
};

function report(overrides: Partial<SandboxReport> = {}): SandboxReport {
  return {
    passed: true,
    summary: '2 of 2 isolation checks passed',
    checks: [
      { id: 'non_root', label: 'Runs as an unprivileged user', passed: true, detail: 'uid 65532' },
      { id: 'no_network', label: 'Cannot reach the network', passed: true, detail: 'no route out' },
    ],
    ...overrides,
  };
}

const LEAKY = report({
  passed: false,
  summary: '1 of 2 isolation checks passed',
  checks: [
    { id: 'non_root', label: 'Runs as an unprivileged user', passed: true, detail: 'uid 65532' },
    {
      id: 'no_network',
      label: 'Cannot reach the network',
      passed: false,
      detail: 'something on the outside answered',
    },
  ],
});

/** Services where one finished run was given a container. */
function withSandboxedRun(detailOverrides: Partial<ExecutionDetail>, base = testServices()): Services {
  return {
    ...base,
    executions: {
      ...base.executions,
      async get(id: string) {
        const detail = await base.executions.get(id);
        return detail && id === FINISHED ? { ...detail, ...detailOverrides } : detail;
      },
    },
  };
}

describe('the sandbox on an execution', () => {
  it('shows each guarantee the container kept', async () => {
    renderApp(
      `/executions/${FINISHED}`,
      withSandboxedRun({ runtime: 'sandbox', sandboxReport: report() }),
    );

    const checks = await screen.findByRole('list', { name: 'Isolation checks' });
    expect(within(checks).getByText('Cannot reach the network')).toBeInTheDocument();
    expect(screen.getByText('2 of 2 isolation checks passed')).toBeInTheDocument();
    expect(screen.getByText('Isolated')).toBeInTheDocument();
    expect(screen.getByText('Sandbox', { selector: 'span' })).toBeInTheDocument();
  });

  it('names the guarantee a container broke', async () => {
    renderApp(
      `/executions/${FINISHED}`,
      withSandboxedRun({
        status: 'FAILED',
        sandboxReport: LEAKY,
        error: { code: 'sandbox_unsafe', message: 'The sandbox did not hold: Cannot reach the network.' },
      }),
    );

    const checks = await screen.findByRole('list', { name: 'Isolation checks' });
    expect(within(checks).getByText('something on the outside answered')).toBeInTheDocument();
    expect(within(checks).getByText(': broken')).toBeInTheDocument();
    expect(screen.getByText('Not isolated')).toBeInTheDocument();
    expect(screen.getByText('Error: sandbox_unsafe')).toBeInTheDocument();
  });

  it('claims nothing about isolation for a run that had no container', async () => {
    renderApp(`/executions/${FINISHED}`);

    await screen.findByRole('heading', { level: 1, name: FINISHED });
    expect(
      screen.getByText(/No container was checked for this run, so nothing about its isolation is claimed/),
    ).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Isolation checks' })).not.toBeInTheDocument();
  });
});

describe('the sandbox in settings', () => {
  it('says plainly when runs cannot be isolated', async () => {
    renderApp('/settings?section=runtime', servicesAs('admin'));

    await screen.findByText('Execution sandbox');
    expect(await screen.findByText('No runtime')).toBeInTheDocument();
    expect(screen.getByText('Runs are not isolated here')).toBeInTheDocument();
  });

  it('shows the limits every container is held to', async () => {
    const services = servicesAs('admin');
    renderApp('/settings?section=runtime', {
      ...services,
      runtime: { ...services.runtime, sandbox: () => Promise.resolve(AVAILABLE) },
    });

    expect(await screen.findByText('Runtime available')).toBeInTheDocument();
    expect(screen.getByText('agenthub/sandbox:0.6.0')).toBeInTheDocument();
    expect(screen.getByText('512 MB, no swap')).toBeInTheDocument();
    expect(screen.getByText('64 MB, not executable')).toBeInTheDocument();
    expect(screen.getByText('None')).toBeInTheDocument();
    expect(screen.queryByText('Runs are not isolated here')).not.toBeInTheDocument();
  });

  it('tells people when isolation is mandatory', async () => {
    const services = servicesAs('admin');
    renderApp('/settings?section=runtime', {
      ...services,
      runtime: {
        ...services.runtime,
        sandbox: () => Promise.resolve({ ...AVAILABLE, available: false, required: true }),
      },
    });

    expect(await screen.findByText('Runs require a verified sandbox')).toBeInTheDocument();
  });

  it('runs the isolation check and shows every result', async () => {
    const services = servicesAs('admin');
    const checkSandbox = vi.fn(() => Promise.resolve({ ...AVAILABLE, report: report() }));
    const { user } = renderApp('/settings?section=runtime', {
      ...services,
      runtime: {
        ...services.runtime,
        sandbox: () => Promise.resolve(AVAILABLE),
        checkSandbox,
      },
    });

    await user.click(await screen.findByRole('button', { name: 'Run isolation check' }));

    const checks = await screen.findByRole('list', { name: 'Isolation checks' });
    expect(checkSandbox).toHaveBeenCalledTimes(1);
    expect(within(checks).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('Isolated')).toBeInTheDocument();
  });

  it('does not dress up a demo check as a pass', async () => {
    const { user } = renderApp('/settings?section=runtime', servicesAs('admin'));

    await user.click(await screen.findByRole('button', { name: 'Run isolation check' }));

    const checks = await screen.findByRole('list', { name: 'Isolation checks' });
    expect(within(checks).getByText('A container runtime is available')).toBeInTheDocument();
    expect(screen.getByText('Not isolated')).toBeInTheDocument();
  });

  it('will not let a member start a container', async () => {
    renderApp('/settings?section=runtime', servicesAs('member'));

    await screen.findByText('Execution sandbox');
    expect(await screen.findByText('Your role cannot start containers')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run isolation check' })).toBeDisabled();
  });
});
