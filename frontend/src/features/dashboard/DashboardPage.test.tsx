import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

describe('dashboard', () => {
  it('shows overview metrics computed from demo data', async () => {
    renderApp('/dashboard');

    const metrics = await screen.findByRole('region', { name: 'Overview metrics' });
    expect(within(metrics).getByRole('link', { name: /Total agents\s*8/ })).toBeInTheDocument();
    expect(within(metrics).getByRole('link', { name: /Active agents\s*5/ })).toBeInTheDocument();
    expect(within(metrics).getByRole('link', { name: /Running executions\s*3/ })).toBeInTheDocument();
    expect(within(metrics).getByRole('link', { name: /Completed executions\s*6/ })).toBeInTheDocument();
    expect(within(metrics).getByRole('link', { name: /Failed executions\s*3/ })).toBeInTheDocument();
    expect(within(metrics).getByRole('link', { name: /Security alerts\s*4/ })).toBeInTheDocument();
  });

  it('labels the page and system status as demonstration data', async () => {
    renderApp('/dashboard');

    expect(await screen.findByText(/do not reflect a real backend/)).toBeInTheDocument();
    expect(await screen.findByText('Agent Runtime')).toBeInTheDocument();
    expect(screen.getByText(/These are not real health checks/)).toBeInTheDocument();
  });

  it('lists recent executions with links to their details', async () => {
    renderApp('/dashboard');

    const table = await screen.findByRole('table', { name: 'Recent executions' });
    expect(within(table).getByRole('link', { name: 'exe_7f3a91c2' })).toHaveAttribute('href', '/executions/exe_7f3a91c2');
    expect(within(table).getByText('Running')).toBeInTheDocument();
  });
});
