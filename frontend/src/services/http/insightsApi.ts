import type {
  AlertService,
  AnalyticsService,
  SecurityService,
} from '@/services/contracts';
import type {
  AlertRecord,
  AnalyticsSummary,
  ExecutionStatus,
  ID,
  PlatformPolicy,
  SecurityEvent,
  SecurityOverview,
  SystemComponentStatus,
} from '@/types/domain';
import { EXECUTION_STATUSES } from '@/types/domain';
import { apiRequest } from './client';
import {
  AlertRecordSchema,
  AnalyticsSummarySchema,
  SecurityEventSchema,
  SecurityOverviewSchema,
  SystemStatusSchema,
  pageSchema,
} from './schemas';
import { z } from 'zod';

/**
 * What the platform enforces, stated as fact. These are properties of the code,
 * not per-organization data, so they are listed here rather than fetched; each
 * one names the mechanism a reader can check.
 */
export const PLATFORM_POLICIES: PlatformPolicy[] = [
  {
    id: 'pol_deny_by_default',
    name: 'Nothing is granted by default',
    description: 'Every capability starts denied; installs grant only what an administrator chooses.',
    enforcement: 'enforced',
  },
  {
    id: 'pol_policy_engine',
    name: 'Every tool call is decided by policy',
    description: "Grants, egress mode, allowed domains and approval-by-risk, decided outside the model.",
    enforcement: 'enforced',
  },
  {
    id: 'pol_egress',
    name: 'Outbound requests are allow-listed and read-only',
    description: 'HTTPS GET to an allowed domain on a public address only; no redirects; pinned connections.',
    enforcement: 'enforced',
  },
  {
    id: 'pol_untrusted_content',
    name: 'Fetched content is untrusted',
    description: 'Handed to the model marked as data, never followed as instructions.',
    enforcement: 'enforced',
  },
  {
    id: 'pol_sandbox',
    name: 'Runs get a verified sandbox',
    description: 'A container is checked from the inside before a run; one that fails a check fails the run.',
    enforcement: 'enforced',
  },
  {
    id: 'pol_audit',
    name: 'Security decisions are audited',
    description: 'Append-only; administrators can read it and nothing can edit it.',
    enforcement: 'enforced',
  },
  {
    id: 'pol_alerts',
    name: 'Anomalies raise alerts',
    description: 'Failing runs, stalled work, policy and egress spikes, sandbox failures and spend.',
    enforcement: 'monitoring',
  },
];

export const httpSecurityService: SecurityService = {
  overview(): Promise<SecurityOverview> {
    return apiRequest('/api/v1/security/overview', SecurityOverviewSchema);
  },
  events(): Promise<SecurityEvent[]> {
    return apiRequest('/api/v1/security/events?limit=50', z.array(SecurityEventSchema));
  },
  policies(): Promise<PlatformPolicy[]> {
    return Promise.resolve(PLATFORM_POLICIES);
  },
};

export const httpAnalyticsService: AnalyticsService = {
  async summary(): Promise<AnalyticsSummary> {
    const raw = await apiRequest('/api/v1/analytics/summary?days=14', AnalyticsSummarySchema);
    const breakdown = Object.fromEntries(EXECUTION_STATUSES.map((status) => [status, 0])) as Record<
      ExecutionStatus,
      number
    >;
    for (const [status, count] of Object.entries(raw.statusBreakdown)) {
      if (status in breakdown) breakdown[status as ExecutionStatus] = count;
    }
    return { ...raw, statusBreakdown: breakdown };
  },
};

export async function fetchComponentStatus(): Promise<SystemComponentStatus[]> {
  const status = await apiRequest('/api/v1/system/status', SystemStatusSchema);
  return status.components;
}

const AlertPageSchema = pageSchema(AlertRecordSchema);

export const httpAlertService: AlertService = {
  async list(state?: AlertRecord['state']): Promise<AlertRecord[]> {
    const query = new URLSearchParams({ limit: '100' });
    if (state) query.set('state', state);
    const page = await apiRequest(`/api/v1/alerts?${query.toString()}`, AlertPageSchema);
    return page.items;
  },
  resolve(id: ID): Promise<AlertRecord> {
    return apiRequest(`/api/v1/alerts/${encodeURIComponent(id)}/resolve`, AlertRecordSchema, {
      method: 'POST',
    });
  },
};
