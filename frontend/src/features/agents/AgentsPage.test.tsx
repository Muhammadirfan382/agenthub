import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

describe('agents list', () => {
  it('renders every demo agent with status, verification and risk', async () => {
    renderApp('/agents');

    const table = await screen.findByRole('table', { name: 'Agents' });
    expect(within(table).getAllByRole('row')).toHaveLength(9); // header + 8 agents
    const row = within(table).getByRole('link', { name: 'Threat Triage' }).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText('Active')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('Verified')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('High risk')).toBeInTheDocument();
  });

  it('filters by search text', async () => {
    const { user } = renderApp('/agents');
    await screen.findByRole('table', { name: 'Agents' });

    await user.type(screen.getByRole('searchbox', { name: 'Search agents' }), 'threat');

    await waitFor(() => expect(screen.queryByRole('link', { name: 'Research Scout' })).not.toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'Threat Triage' })).toBeInTheDocument();
    expect(screen.getByText('1 agent')).toBeInTheDocument();
  });

  it('filters by status and shows an empty state when nothing matches', async () => {
    const { user } = renderApp('/agents');
    await screen.findByRole('table', { name: 'Agents' });

    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by status' }), 'disabled');
    await waitFor(() => expect(screen.getByText('1 agent')).toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'Invoice Reconciler' })).toBeInTheDocument();

    await user.type(screen.getByRole('searchbox', { name: 'Search agents' }), 'no-such-agent');
    expect(await screen.findByText('No agents match your filters')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(screen.getByText('8 agents')).toBeInTheDocument());
  });

  it('sorts by risk from the column header', async () => {
    const { user } = renderApp('/agents');
    const table = await screen.findByRole('table', { name: 'Agents' });

    await user.click(within(table).getByRole('button', { name: /Risk/ }));

    await waitFor(() => {
      const firstDataRow = within(screen.getByRole('table', { name: 'Agents' })).getAllByRole('row')[1];
      expect(within(firstDataRow as HTMLElement).getByRole('link', { name: 'Incident Responder' })).toBeInTheDocument();
    });
  });

  it('deletes an agent after confirmation and shows success feedback', async () => {
    const { user } = renderApp('/agents');
    await screen.findByRole('table', { name: 'Agents' });

    await user.click(screen.getByRole('button', { name: 'Actions for Research Scout' }));
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }));

    const dialog = screen.getByRole('dialog', { name: 'Delete Research Scout?' });
    await user.click(within(dialog).getByRole('button', { name: 'Delete agent' }));

    expect(await screen.findByText('Research Scout deleted')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Research Scout' })).not.toBeInTheDocument());
    expect(screen.getByText('7 agents')).toBeInTheDocument();
  });

  it('does not allow executing an agent that is not active', async () => {
    const { user } = renderApp('/agents');
    await screen.findByRole('table', { name: 'Agents' });

    await user.click(screen.getByRole('button', { name: 'Actions for SEO Auditor' }));
    expect(screen.getByRole('menuitem', { name: 'Execute (agent not active)' })).toBeDisabled();
  });
});
