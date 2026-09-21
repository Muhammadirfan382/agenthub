import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

describe('security dashboard', () => {
  it('clearly labels the data as demonstration security data', async () => {
    renderApp('/security');
    expect(await screen.findByRole('heading', { level: 1, name: 'Security' })).toBeInTheDocument();
    expect(screen.getByText(/Everything on this page is demonstration data/)).toBeInTheDocument();
  });

  it('shows all four risk classifications with agent counts', async () => {
    renderApp('/security');
    const card = (await screen.findByRole('heading', { name: 'Agent risk levels' })).closest('div.rounded-lg') as HTMLElement;
    for (const [level, count] of [['Low', 3], ['Medium', 2], ['High', 2], ['Critical', 1]] as const) {
      expect(within(card).getByRole('progressbar', { name: `${level} risk agents` })).toHaveAttribute('aria-valuenow', String(count));
    }
  });

  it('shows open alerts, recent events, permissions and policies', async () => {
    renderApp('/security');

    const summary = await screen.findByRole('region', { name: 'Security summary' });
    expect(within(summary).getByText('Open alerts').parentElement?.parentElement).toHaveTextContent('4');

    const events = await screen.findByRole('table', { name: 'Recent security events' });
    expect(within(events).getByText('Permission escalation attempt')).toBeInTheDocument();

    expect(screen.getByRole('table', { name: /Permission overview/ })).toBeInTheDocument();
    expect(screen.getByText('Critical: Permission escalation attempt')).toBeInTheDocument();
    expect(screen.getByText('Deny by default')).toBeInTheDocument();
  });
});
