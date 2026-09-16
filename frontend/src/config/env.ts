import { z } from 'zod';
import type { DataSource } from '@/services/contracts';

/**
 * Public, build-time configuration. Values here end up in the browser bundle,
 * so this schema must never contain secrets.
 */
const EnvSchema = z.object({
  VITE_API_BASE_URL: z
    .string()
    .trim()
    .default('')
    .refine((value) => value === '' || /^https?:\/\/[^\s]+$/i.test(value), {
      message: 'VITE_API_BASE_URL must be empty or an http(s) URL.',
    })
    .transform((value) => value.replace(/\/+$/, '')),
  VITE_DATA_SOURCE: z.enum(['demo', 'api']).default('demo'),
});

export interface AppConfig {
  /** Backend base URL without a trailing slash; empty string means same-origin. */
  apiBaseUrl: string;
  /** Service implementation the app starts with. Users can switch it at runtime. */
  dataSource: DataSource;
}

export function parseConfig(raw: Record<string, unknown>): AppConfig {
  const parsed = EnvSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(`Invalid frontend configuration: ${parsed.error.issues.map((i) => i.message).join(' ')}`);
  }
  return { apiBaseUrl: parsed.data.VITE_API_BASE_URL, dataSource: parsed.data.VITE_DATA_SOURCE };
}

export const appConfig: AppConfig = parseConfig({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  VITE_DATA_SOURCE: import.meta.env.VITE_DATA_SOURCE,
});
