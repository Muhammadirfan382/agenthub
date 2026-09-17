import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { renderApp, servicesAs, testServices } from '@/test/renderApp';

const CODE_REVIEWER = 'ver_demo_code_reviewer';
const INSTALLED = 'ver_demo_support_drafter';

describe('marketplace', () => {
  it('lists agents with their version and publisher', async () => {
    renderApp('/marketplace');

    expect(await screen.findByText('Code Review Assistant')).toBeInTheDocument();
    expect(screen.getAllByText('Beacon Tools').length).toBeGreaterThan(0);
    expect(screen.getByText('v3.0.2')).toBeInTheDocument();
  });

  it('filters down to what is installed', async () => {
    const { user } = renderApp('/marketplace');
    await screen.findByText('Code Review Assistant');

    await user.click(screen.getByRole('tab', { name: 'Installed' }));

    expect(await screen.findByText('Support Reply Drafter')).toBeInTheDocument();
    expect(screen.queryByText('Code Review Assistant')).not.toBeInTheDocument();
  });
});

describe('a listing', () => {
  it('shows what the agent asks for before anything is granted', async () => {
    renderApp(`/marketplace/${CODE_REVIEWER}`);

    await screen.findByRole('heading', { level: 1, name: 'Code Review Assistant' });
    expect(screen.getByText('What this agent asks for')).toBeInTheDocument();
    // The install panel starts at nothing granted.
    expect(await screen.findByText(/0 of \d/)).toBeInTheDocument();
  });

  it('sends only the capabilities that were granted', async () => {
    const services = testServices();
    const install = vi.fn(services.installations.install);
    const withSpy: Services = {
      ...services,
      installations: { ...services.installations, install },
    };

    const { user } = renderApp(`/marketplace/${CODE_REVIEWER}`, withSpy);
    await screen.findByRole('heading', { level: 1, name: 'Code Review Assistant' });

    const [firstLevel] = await screen.findAllByRole('combobox', { name: /Grant level for/ });
    await user.selectOptions(firstLevel as HTMLSelectElement, 'read_only');
    const [firstScope] = screen.getAllByRole('textbox', { name: /Scope for/ });
    await user.type(firstScope as HTMLInputElement, 'Repository checkout only');

    await user.click(screen.getByRole('button', { name: 'Install agent' }));

    expect(install).toHaveBeenCalledTimes(1);
    const input = install.mock.calls[0]?.[0];
    expect(input?.agentVersionId).toBe(CODE_REVIEWER);
    expect(input?.grants).toHaveLength(1);
    expect(input?.grants[0]).toMatchObject({ level: 'read_only', scope: 'Repository checkout only' });
  });

  it('never offers more than the manifest asked for', async () => {
    renderApp(`/marketplace/${CODE_REVIEWER}`);
    await screen.findByRole('heading', { level: 1, name: 'Code Review Assistant' });

    const selects = await screen.findAllByRole('combobox', { name: /Grant level for/ });
    for (const select of selects) {
      const options = within(select as HTMLSelectElement)
        .getAllByRole('option')
        .map((option) => (option as HTMLOptionElement).value);
      expect(options[0]).toBe('denied');
      // 'allowed' only appears where the publisher asked for it.
      expect(options).not.toContain('unknown');
    }
  });

  it('shows what was granted for an installed agent', async () => {
    renderApp(`/marketplace/${INSTALLED}`);

    await screen.findByRole('heading', { level: 1, name: 'Support Reply Drafter' });
    expect(await screen.findByText('What you granted')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Uninstall' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Install agent' })).not.toBeInTheDocument();
  });

  it('does not let a viewer install', async () => {
    renderApp(`/marketplace/${CODE_REVIEWER}`, servicesAs('viewer'));

    await screen.findByRole('heading', { level: 1, name: 'Code Review Assistant' });
    expect(await screen.findByText('Your role cannot install agents')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Install agent' })).toBeDisabled();
  });
});
