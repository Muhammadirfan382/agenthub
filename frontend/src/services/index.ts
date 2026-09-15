import type { Services } from './contracts';
import { createDemoServices } from './demo/createDemoServices';

/**
 * Builds the service layer used by the app.
 *
 * Phase 1 only has demo implementations. In Phase 2, HTTP implementations of
 * the same contracts (built on `services/http/client.ts`) replace them here.
 * Components receive services through `ServicesProvider` and never need to
 * change.
 */
export function createServices(): Services {
  return createDemoServices();
}

export type * from './contracts';
