import type { DailyPoint, SystemComponentStatus } from '@/types/domain';
import { daysAgo } from './time';

/*
 * DEMO DATA. These component states are simulated. They do not reflect the
 * health of any real service; real health checks arrive with the backend.
 */
export const demoComponentStatus: SystemComponentStatus[] = [
  { id: 'api', name: 'API', state: 'operational', detail: 'Simulated state for the demo.' },
  { id: 'runtime', name: 'Agent Runtime', state: 'degraded', detail: 'Simulated degraded state to illustrate alerts.' },
  { id: 'database', name: 'Database', state: 'operational', detail: 'Simulated state for the demo.' },
  { id: 'security', name: 'Security', state: 'operational', detail: 'Simulated state for the demo.' },
];

const executionsSeries = [38, 42, 35, 51, 47, 29, 24, 55, 61, 58, 49, 33, 27, 64];
const tokensSeries = [410, 455, 390, 560, 520, 300, 260, 610, 690, 640, 540, 350, 290, 720];

const toSeries = (values: number[], scale = 1): DailyPoint[] =>
  values.map((value, index) => ({ date: daysAgo(values.length - 1 - index), value: value * scale }));

export const demoExecutionsPerDay: DailyPoint[] = toSeries(executionsSeries);
/** Thousands of tokens per day. */
export const demoTokensPerDay: DailyPoint[] = toSeries(tokensSeries, 1000);
