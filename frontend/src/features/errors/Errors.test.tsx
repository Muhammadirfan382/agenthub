import { render, screen } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/renderApp';
import RouteErrorPage from './RouteErrorPage';

describe('404 page', () => {
  it('renders for unknown routes inside the application shell', async () => {
    renderApp('/this/route/does-not-exist');

    expect(await screen.findByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to dashboard' })).toHaveAttribute('href', '/dashboard');
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
  });
});

describe('route error boundary', () => {
  it('shows a recovery page without leaking error details', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    function Broken(): never {
      throw new Error('internal secret stack detail');
    }
    const router = createMemoryRouter([{ path: '/', element: <Broken />, errorElement: <RouteErrorPage /> }]);
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Something went wrong' })).toBeInTheDocument();
    expect(screen.queryByText(/internal secret stack detail/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeInTheDocument();
  });
});
