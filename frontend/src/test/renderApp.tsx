import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { AppProviders } from '@/app/AppProviders';
import { createQueryClient } from '@/app/queryClient';
import { routes } from '@/app/routes';
import type { Services } from '@/services/contracts';
import { createDemoServices } from '@/services/demo/createDemoServices';

/** Fresh demo services with no simulated latency. */
export function testServices(): Services {
  return createDemoServices({ latencyMs: 0 });
}

/** Renders the real route table at `path` with isolated state. */
export function renderApp(path = '/dashboard', services: Services = testServices()) {
  const queryClient = createQueryClient({ retry: 0 });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const user = userEvent.setup();
  const utils = render(
    <AppProviders services={services} queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...utils, user, router, services };
}

export const never = <T,>(): Promise<T> => new Promise<T>(() => undefined);
