import { z } from 'zod';
import { appConfig, type AppConfig } from '@/config/env';

/**
 * The single place where the frontend talks HTTP. Service implementations use
 * `apiRequest`; components never call `fetch` directly.
 *
 * - No credentials or API keys are ever attached here. Authentication arrives
 *   in Phase 3 and will use an HttpOnly session managed by the backend.
 * - Every response is validated against a Zod schema before it reaches the UI.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 10_000;

/** The error envelope the backend returns for every failure. */
const ErrorBodySchema = z.object({ code: z.string().max(64), message: z.string().max(500) });

export function buildUrl(path: string, config: AppConfig = appConfig): string {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new Error(`API paths must be absolute paths on the API origin, received "${path}".`);
  }
  return `${config.apiBaseUrl}${path}`;
}

/** Prefers the backend's own message, so users see "Name already in use", not "HTTP 409". */
async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  const parsed = ErrorBodySchema.safeParse(body);
  if (parsed.success) {
    return new ApiError(parsed.data.message, response.status, parsed.data.code);
  }
  return new ApiError(`The AgentHub API responded with HTTP ${response.status}.`, response.status, `http_${response.status}`);
}

async function send(path: string, options: RequestOptions, config: AppConfig): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const onExternalAbort = () => controller.abort();
  options.signal?.addEventListener('abort', onExternalAbort, { once: true });

  try {
    let response: Response;
    try {
      response = await fetch(buildUrl(path, config), {
        method: options.method ?? 'GET',
        headers: {
          Accept: 'application/json',
          ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: 'same-origin',
        signal: controller.signal,
      });
    } catch {
      throw new ApiError('The AgentHub API could not be reached.', 0, 'network_error');
    }

    if (!response.ok) {
      throw await toApiError(response);
    }
    return response;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', onExternalAbort);
  }
}

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
  config: AppConfig = appConfig,
): Promise<T> {
  const response = await send(path, options, config);

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError('The AgentHub API returned a response that is not JSON.', response.status, 'invalid_json');
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiError('The AgentHub API returned an unexpected response.', response.status, 'invalid_response');
  }
  return parsed.data;
}

/** For endpoints that answer with no content, such as DELETE. */
export async function apiRequestVoid(
  path: string,
  options: RequestOptions = {},
  config: AppConfig = appConfig,
): Promise<void> {
  await send(path, options, config);
}
