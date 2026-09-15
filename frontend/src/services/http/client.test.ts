import { describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { parseConfig } from '@/config/env';
import { ApiError, apiRequest, buildUrl } from './client';

const schema = z.object({ status: z.literal('ok') });
const config = { apiBaseUrl: 'https://api.example.com' };

function stubFetch(response: Partial<Response> | Error) {
  const fetchMock = vi.fn(() => (response instanceof Error ? Promise.reject(response) : Promise.resolve(response as Response)));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('http client', () => {
  it('builds URLs from the configured base and rejects protocol-relative or relative paths', () => {
    expect(buildUrl('/api/v1/health', config)).toBe('https://api.example.com/api/v1/health');
    expect(() => buildUrl('//evil.example.com/x', config)).toThrow();
    expect(() => buildUrl('api/v1/health', config)).toThrow();
  });

  it('returns validated data without sending credentials headers', async () => {
    const fetchMock = stubFetch({ ok: true, status: 200, json: () => Promise.resolve({ status: 'ok' }) });
    await expect(apiRequest('/api/v1/health', schema, {}, config)).resolves.toEqual({ status: 'ok' });
    const init = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init[1].credentials).toBe('same-origin');
    expect(JSON.stringify(init[1].headers)).not.toMatch(/authorization/i);
  });

  it('rejects responses that do not match the schema', async () => {
    stubFetch({ ok: true, status: 200, json: () => Promise.resolve({ status: 'compromised' }) });
    await expect(apiRequest('/x', schema, {}, config)).rejects.toMatchObject({ code: 'invalid_response' });
  });

  it('maps HTTP and network failures to typed errors', async () => {
    stubFetch({ ok: false, status: 503, json: () => Promise.resolve({}) });
    await expect(apiRequest('/x', schema, {}, config)).rejects.toMatchObject({ status: 503, code: 'http_503' });

    stubFetch(new TypeError('Failed to fetch'));
    const error = await apiRequest('/x', schema, {}, config).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'network_error' });
  });
});

describe('frontend configuration', () => {
  it('accepts empty or http(s) base URLs and strips trailing slashes', () => {
    expect(parseConfig({}).apiBaseUrl).toBe('');
    expect(parseConfig({ VITE_API_BASE_URL: 'https://api.example.com/' }).apiBaseUrl).toBe('https://api.example.com');
  });

  it('rejects non-http schemes', () => {
    expect(() => parseConfig({ VITE_API_BASE_URL: 'javascript:alert(1)' })).toThrow(/must be empty or an http\(s\) URL/);
  });
});
