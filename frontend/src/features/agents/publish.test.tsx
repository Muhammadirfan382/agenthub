import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { renderApp, servicesAs, testServices } from '@/test/renderApp';

const AGENT = '/agents/agt_research_scout';

describe('publishing an agent', () => {
  it('freezes the current configuration with a changelog and a visibility', async () => {
    const services = testServices();
    const publish = vi.fn(services.agents.publish);
    const withSpy: Services = { ...services, agents: { ...services.agents, publish } };

    const { user } = renderApp(AGENT, withSpy);
    await screen.findByRole('heading', { level: 1, name: 'Research Scout' });

    await user.click(screen.getByRole('button', { name: 'Publish' }));
    await user.type(
      await screen.findByRole('textbox', { name: /What changed/ }),
      'Tighter source allow-list',
    );
    await user.selectOptions(screen.getByRole('combobox', { name: /Marketplace visibility/ }), 'public');
    await user.click(screen.getByRole('button', { name: 'Publish version' }));

    expect(publish).toHaveBeenCalledWith('agt_research_scout', {
      changelog: ['Tighter source allow-list'],
      visibility: 'public',
    });
  });

  it('refuses to publish the same version twice', async () => {
    const { user } = renderApp(AGENT);
    await screen.findByRole('heading', { level: 1, name: 'Research Scout' });

    // The demo agent already has its current version published.
    await user.click(screen.getByRole('button', { name: 'Publish' }));
    await user.click(await screen.findByRole('button', { name: 'Publish version' }));

    expect(await screen.findByText(/already published/i)).toBeInTheDocument();
  });

  it('hides publishing from a viewer', async () => {
    renderApp(AGENT, servicesAs('viewer'));

    await screen.findByRole('heading', { level: 1, name: 'Research Scout' });
    expect(screen.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
  });
});
