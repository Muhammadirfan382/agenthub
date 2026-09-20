import type { AuditService } from '@/services/contracts';
import type { AuditEvent, AuditQuery } from '@/types/domain';
import { apiRequest } from './client';
import { AuditEventSchema, pageSchema } from './schemas';

const AuditPageSchema = pageSchema(AuditEventSchema);
const PAGE_LIMIT = 100;

/** The audit log, served read-only by `GET /api/v1/audit`. */
export const httpAuditService: AuditService = {
  async list(query: AuditQuery = {}): Promise<AuditEvent[]> {
    const params = new URLSearchParams({ limit: String(PAGE_LIMIT) });
    if (query.action) params.set('action', query.action);
    if (query.outcome) params.set('outcome', query.outcome);
    const page = await apiRequest(`/api/v1/audit?${params.toString()}`, AuditPageSchema);
    return page.items;
  },
};
