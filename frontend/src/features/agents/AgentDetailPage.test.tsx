import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

describe('agent details', () => {
  it('shows the overview with creator, version, category and tags', async () => {
    renderApp('/agents/agt_research_scout');

    expect(await screen.findByRole('heading', { level: 1, name: 'Research Scout' })).toBeInTheDocument();
    // Shown in the header badge and in the overview details.
    expect(screen.getAllByText('v2.3.1')).toHaveLength(2);
    expect(screen.getByText('Low risk')).toBeInTheDocument();
    expect(screen.getAllByText('Maya Chen').length).toBeGreaterThan(0);
    expect(screen.getByText('citations')).toBeInTheDocument();
    for (const action of ['Execute', 'Deploy', 'Disable']) {
      expect(screen.getByRole('button', { name: action })).toBeInTheDocument();
    }
    expect(screen.getByRole('link', { name: 'Edit' })).toHaveAttribute('href', '/agents/agt_research_scout/edit');
  });

  it('shows permitted capabilities with permission indicators', async () => {
    const { user } = renderApp('/agents/agt_research_scout');
    await screen.findByRole('heading', { level: 1, name: 'Research Scout' });

    await user.click(screen.getByRole('tab', { name: 'Capabilities' }));

    const granted = screen.getByRole('heading', { name: 'Permitted capabilities (3)' }).parentElement as HTMLElement;
    expect(within(granted).getByText('Web access')).toBeInTheDocument();
    expect(within(granted).getByText('Restricted')).toBeInTheDocument();
    expect(within(granted).getByText('Read only')).toBeInTheDocument();
    expect(screen.getByText(/nothing shown here is a security control/)).toBeInTheDocument();
  });

  it('shows version history and demo security data', async () => {
    const { user } = renderApp('/agents/agt_incident_responder');
    await screen.findByRole('heading', { level: 1, name: 'Incident Responder' });

    await user.click(screen.getByRole('tab', { name: 'Versions' }));
    expect(screen.getByText('v1.0.0-rc.1')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Security' }));
    expect(screen.getByText('Demo security data')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Risk score' })).toHaveAttribute('aria-valuenow', '88');
    expect(screen.getByText('Permission minimisation')).toBeInTheDocument();
  });

  it('shows a not-found state for an unknown agent', async () => {
    renderApp('/agents/does-not-exist');
    expect(await screen.findByText('Agent not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to agents' })).toBeInTheDocument();
  });
});
