import { z } from 'zod';
import type { BackendHealth } from '@/types/domain';
import { apiRequest } from './client';

const BackendHealthSchema = z.object({
  status: z.literal('ok'),
  service: z.string().max(100),
  version: z.string().max(50),
  message: z.string().max(200),
});

/** The only real backend call in Phase 1: the Phase 0 liveness endpoint. */
export function fetchBackendHealth(): Promise<BackendHealth> {
  return apiRequest('/api/v1/health', BackendHealthSchema, { timeoutMs: 5000 });
}
