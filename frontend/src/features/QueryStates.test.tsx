import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { never, renderApp, testServices } from '@/test/renderApp';

describe('loading states', () => {
  it('announces loading while dashboard data is pending', async () => {
    const services = testServices();
    services.system.dashboardSummary = () => never();
    services.system.componentStatus = () => never();
    services.executions.list = () => never();
    services.agents.list = () => never();
    renderApp('/dashboard', services);

    expect(await screen.findByText('Loading metrics…')).toBeInTheDocument();
    expect(screen.getByText('Loading recent activity…')).toBeInTheDocument();
    expect(screen.getByText('Loading system status…')).toBeInTheDocument();
  });

  it('shows a loading state on the agents page', async () => {
    const services = testServices();
    services.agents.list = () => never();
    renderApp('/agents', services);

    const status = await screen.findByText('Loading agents…');
    expect(status.closest('[role="status"]')).not.toBeNull();
  });
});

describe('error states', () => {
  it('shows an error with a retry that recovers', async () => {
    const services = testServices();
    const realList = services.agents.list.bind(services.agents);
    const list = vi.fn().mockRejectedValueOnce(new Error('network down')).mockImplementation(realList);
    services.agents.list = list;
    const { user } = renderApp('/agents', services);

    expect(await screen.findByRole('heading', { name: 'Agents could not be loaded' })).toBeInTheDocument();
    expect(screen.queryByText('network down')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByRole('table', { name: 'Agents' })).toBeInTheDocument());
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('never renders a failed request as an empty list', async () => {
    const services = testServices();
    services.executions.list = () => Promise.reject(new Error('boom'));
    renderApp('/executions', services);

    expect(await screen.findByRole('heading', { name: 'Executions could not be loaded' })).toBeInTheDocument();
    expect(screen.queryByText('No executions yet')).not.toBeInTheDocument();
  });
});
