import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

describe('application shell', () => {
  it('renders the layout, navigation and demo indicator', async () => {
    renderApp('/dashboard');

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toBeInTheDocument();
    expect(screen.getByText('Demo mode')).toBeInTheDocument();

    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    for (const label of ['Dashboard', 'Agents', 'Marketplace', 'Executions', 'Security', 'Analytics', 'Settings']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page');
  });

  it('redirects the root path to the dashboard', async () => {
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/dashboard');
  });

  it('navigates between pages from the sidebar', async () => {
    const { user } = renderApp('/dashboard');
    await screen.findByRole('heading', { level: 1, name: 'Dashboard' });

    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    await user.click(within(nav).getByRole('link', { name: 'Agents' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Agents' })).toBeInTheDocument();

    await user.click(within(nav).getByRole('link', { name: 'Security' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Security' })).toBeInTheDocument();
  });

  it('opens the mobile navigation drawer and closes it after navigating', async () => {
    const { user } = renderApp('/dashboard');
    await screen.findByRole('heading', { level: 1, name: 'Dashboard' });

    await user.click(screen.getByRole('button', { name: 'Open navigation' }));
    const drawer = screen.getByRole('dialog', { name: 'Navigation' });
    await user.click(within(drawer).getByRole('link', { name: 'Marketplace' }));

    expect(await screen.findByRole('heading', { level: 1, name: 'Marketplace' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Navigation' })).not.toBeInTheDocument();
  });
});
