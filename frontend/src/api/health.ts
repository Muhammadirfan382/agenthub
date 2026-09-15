/** Shape returned by the backend's `GET /api/v1/health` endpoint. */
export interface BackendHealth {
  status: 'ok';
  service: string;
  version: string;
  message: string;
}

export const HEALTH_ENDPOINT = '/api/v1/health';

/**
 * Validates the response at runtime. The TypeScript type alone proves nothing
 * about what the network returned, so anything unexpected is rejected.
 */
export function isBackendHealth(value: unknown): value is BackendHealth {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.status === 'ok' &&
    typeof candidate.service === 'string' &&
    typeof candidate.version === 'string' &&
    typeof candidate.message === 'string'
  );
}

export async function fetchBackendHealth(signal?: AbortSignal): Promise<BackendHealth> {
  const response = await fetch(HEALTH_ENDPOINT, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'omit',
    signal,
  });

  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}.`);
  }

  const body: unknown = await response.json();
  if (!isBackendHealth(body)) {
    throw new Error('Health check returned an unexpected response.');
  }
  return body;
}
