import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Services } from '@/services/contracts';
import { ApiError } from '@/services/http/client';
import { renderApp, servicesAs, sessionFor, signedOutServices, testServices } from '@/test/renderApp';

describe('signed out', () => {
  it('sends a visitor to the sign-in page instead of the dashboard', async () => {
    const { router } = renderApp('/dashboard', signedOutServices());

    expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
  });

  it('protects every page behind the shell', async () => {
    renderApp('/agents/create', signedOutServices());

    expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Create agent' })).not.toBeInTheDocument();
  });

  it('signs in and continues to the page that was asked for', async () => {
    const services = signedOutServices();
    const session = sessionFor('admin');
    const login = vi.fn(() => Promise.resolve(session));
    const withLogin: Services = { ...services, auth: { ...services.auth, login } };

    const { user, router } = renderApp('/agents', withLogin);

    await screen.findByRole('heading', { level: 1, name: 'Sign in' });
    await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
    await user.type(screen.getByLabelText(/password/i), 'a-long-enough-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(login).toHaveBeenCalledWith({
      email: 'admin@example.com',
      password: 'a-long-enough-password',
    });
    await waitFor(() => expect(router.state.location.pathname).toBe('/agents'));
  });

  it('shows the reason the API gave for refusing', async () => {
    const services = signedOutServices();
    const login = vi.fn(() =>
      Promise.reject(new ApiError('Incorrect email or password.', 401, 'unauthenticated')),
    );
    const withLogin: Services = { ...services, auth: { ...services.auth, login } };

    const { user } = renderApp('/login', withLogin);

    await screen.findByRole('heading', { level: 1, name: 'Sign in' });
    await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrong-password-value');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Incorrect email or password.')).toBeInTheDocument();
  });

  it('asks for both fields before calling the API', async () => {
    const services = signedOutServices();
    const login = vi.fn();
    const { user } = renderApp('/login', { ...services, auth: { ...services.auth, login } });

    await screen.findByRole('heading', { level: 1, name: 'Sign in' });
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });
});

describe('an expired session', () => {
  it('returns the user to sign-in when the API stops accepting the session', async () => {
    const services = testServices();
    const agents = {
      ...services.agents,
      list: () => Promise.reject(new ApiError('Your session is no longer valid.', 401, 'unauthenticated')),
    };

    const { router } = renderApp('/agents', { ...services, agents });

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
  });
});

describe('role-aware controls', () => {
  it('offers agent creation to a member', async () => {
    renderApp('/agents', servicesAs('member'));

    const links = await screen.findAllByRole('link', { name: /create agent/i });
    expect(links.length).toBeGreaterThan(0);
  });

  it('hides agent creation from a viewer', async () => {
    renderApp('/agents', servicesAs('viewer'));

    await screen.findByRole('heading', { level: 1, name: 'Agents' });
    expect(screen.queryByRole('link', { name: /create agent/i })).not.toBeInTheDocument();
  });

  it('hides destructive actions from a viewer', async () => {
    const { user } = renderApp('/agents', servicesAs('viewer'));

    await screen.findByRole('heading', { level: 1, name: 'Agents' });
    const menus = await screen.findAllByRole('button', { name: /actions for/i });
    await user.click(menus[0] as HTMLElement);

    expect(await screen.findByRole('menuitem', { name: 'View' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: /execute/i })).not.toBeInTheDocument();
  });
});
