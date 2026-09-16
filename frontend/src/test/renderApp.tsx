import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { AppProviders } from '@/app/AppProviders';
import { createQueryClient } from '@/app/queryClient';
import { routes } from '@/app/routes';
import type { Services } from '@/services/contracts';
import { createDemoServices } from '@/services/demo/createDemoServices';
import type { Organization, Role, SessionInfo } from '@/types/domain';

/** Fresh demo services with no simulated latency, plus any overrides. */
export function testServices(overrides: Partial<Services> = {}): Services {
  return { ...createDemoServices({ latencyMs: 0 }), ...overrides };
}

const testOrganization: Organization = {
  id: 'org_test',
  name: 'Test Workspace',
  slug: 'test-workspace',
};

/** A session for a given role, for tests about what each role may see. */
export function sessionFor(role: Role): SessionInfo {
  return {
    user: {
      id: 'usr_test',
      name: 'Test Person',
      email: 'test.person@example.com',
      status: 'active',
      timezone: 'UTC',
      createdAt: '2026-01-01T00:00:00.000Z',
      lastLoginAt: '2026-09-16T08:00:00.000Z',
    },
    organization: testOrganization,
    role,
    memberships: [{ organization: testOrganization, role }],
    expiresAt: '2026-09-16T20:00:00.000Z',
  };
}

/** Services for a signed-out browser. */
export function signedOutServices(): Services {
  const services = testServices();
  return { ...services, auth: { ...services.auth, session: () => Promise.resolve(null) } };
}

/** Services whose session has the given role. */
export function servicesAs(role: Role): Services {
  const services = testServices();
  return {
    ...services,
    auth: { ...services.auth, session: () => Promise.resolve(sessionFor(role)) },
  };
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
