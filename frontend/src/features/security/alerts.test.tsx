import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { renderApp, servicesAs } from '@/test/renderApp';
import type { AlertRecord, Role } from '@/types/domain';

const firing: AlertRecord = {
  id: 'alr_1',
  rule: 'runs_failing',
  severity: 'critical',
  state: 'firing',
  summary: '3 runs failed in the last 15 minutes.',
  detail: { failed: 3 },
  firstSeen: '2026-09-20T10:00:00.000Z',
  lastSeen: '2026-09-20T10:05:00.000Z',
  resolvedAt: null,
  occurrences: 2,
};

/** Services for `role` that claim live security data and serve these alerts. */
function liveServices(role: Role, alerts: AlertRecord[] = [firing]): Services {
  const base = servicesAs(role);
  return {
    ...base,
    liveResources: [...base.liveResources, 'security', 'alerts', 'status'],
    alerts: {
      list: vi.fn(() => Promise.resolve(alerts)),
      resolve: vi.fn((id: string) => Promise.resolve({ ...firing, id, state: 'resolved' as const })),
    },
  };
}

describe('security page with live data', () => {
  it('says where the data comes from instead of calling it a demonstration', async () => {
    renderApp('/security', liveServices('admin'));

    expect(await screen.findByText(/alerts from rules the backend evaluates/)).toBeInTheDocument();
    expect(screen.queryByText(/Everything on this page is demonstration data/)).not.toBeInTheDocument();
  });

  it('shows firing alerts and lets an administrator resolve one', async () => {
    const services = liveServices('admin');
    const { user } = renderApp('/security', services);

    const alert = await screen.findByText('Critical: 3 runs failed in the last 15 minutes.');
    const item = alert.closest('li') as HTMLElement;
    expect(within(item).getByText(/seen 2 times/)).toBeInTheDocument();

    await user.click(within(item).getByRole('button', { name: 'Resolve' }));

    expect(services.alerts.resolve).toHaveBeenCalledWith('alr_1');
  });

  it('does not offer resolving to a member', async () => {
    renderApp('/security', liveServices('member'));

    await screen.findByText('Critical: 3 runs failed in the last 15 minutes.');
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
  });

  it('says so when nothing is firing', async () => {
    renderApp('/security', liveServices('admin', []));

    expect(await screen.findByText('No alerts firing')).toBeInTheDocument();
  });
});

describe('system status with live data', () => {
  it('drops the demonstration label and disclaimer', async () => {
    renderApp('/dashboard', liveServices('admin'));

    expect(await screen.findByText('Checked by the backend when this card loads.')).toBeInTheDocument();
    expect(screen.queryByText(/These are not real health checks/)).not.toBeInTheDocument();
  });
});
