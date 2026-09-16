import { appConfig } from '@/config/env';
import type { DataSource, Services } from './contracts';
import { createDemoServices } from './demo/createDemoServices';
import { createHttpServices } from './http/createHttpServices';

/**
 * Builds the service layer used by the app.
 *
 * Demo mode answers everything from in-memory demonstration data. API mode
 * talks to the backend for the resources it implements (agents, executions and
 * the dashboard counts derived from them) and keeps demo data for the rest.
 * Components receive services through `ServicesProvider` and never care which.
 */
export function createServices(dataSource: DataSource = appConfig.dataSource): Services {
  return dataSource === 'api' ? createHttpServices() : createDemoServices();
}

export type * from './contracts';
