import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Member, SessionInfo } from '@/types/domain';
import { httpAuthService, httpMemberService } from './authApi';
import { apiRequestVoid } from './client';

const session: SessionInfo = {
  user: {
    id: 'usr_1',
    email: 'admin@example.com',
    name: 'Admin Person',
    status: 'active',
    timezone: 'UTC',
    createdAt: '2026-01-01T00:00:00Z',
    lastLoginAt: '2026-09-16T08:00:00Z',
  },
  organization: { id: 'org_1', name: 'Test Workspace', slug: 'test-workspace' },
  role: 'admin',
  memberships: [
    { organization: { id: 'org_1', name: 'Test Workspace', slug: 'test-workspace' }, role: 'admin' },
  ],
  expiresAt: '2026-09-16T20:00:00Z',
};

const member: Member = {
  id: 'mem_1',
  userId: 'usr_1',
  email: 'admin@example.com',
  name: 'Admin Person',
  role: 'admin',
  status: 'active',
  createdAt: '2026-01-01T00:00:00Z',
  lastLoginAt: null,
};

function stubFetch(...responses: { status?: number; body?: unknown }[]) {
  const fetchMock = vi.fn(() => {
    const next = responses.shift() ?? { status: 200, body: {} };
    const status = next.status ?? 200;
    return Promise.resolve({
      ok: status < 400,
      status,
      json: () =>
        next.body === undefined ? Promise.reject(new Error('no body')) : Promise.resolve(next.body),
    } as Response);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function requestOf(fetchMock: ReturnType<typeof stubFetch>, index = 0) {
  const call = fetchMock.mock.calls[index] as unknown as [string, RequestInit];
  return { url: call[0], init: call[1] };
}

function headerOf(init: RequestInit, name: string): string | undefined {
  return (init.headers as Record<string, string> | undefined)?.[name];
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'agenthub_csrf=; Max-Age=0; path=/';
});

describe('session', () => {
  it('reads the current session', async () => {
    const fetchMock = stubFetch({ body: session });

    await expect(httpAuthService.session()).resolves.toEqual(session);
    expect(requestOf(fetchMock).url).toBe('/api/v1/auth/session');
  });

  it('treats a refused session as signed out, not as an error', async () => {
    stubFetch({ status: 401, body: { code: 'unauthenticated', message: 'Authentication is required.' } });

    await expect(httpAuthService.session()).resolves.toBeNull();
  });

  it('sends credentials in the body and never in the URL', async () => {
    const fetchMock = stubFetch({ body: session });

    await httpAuthService.login({ email: 'admin@example.com', password: 'a-long-password' });

    const { url, init } = requestOf(fetchMock);
    expect(url).toBe('/api/v1/auth/login');
    expect(url).not.toContain('password');
    expect(init.method).toBe('POST');
    expect(init.body).toBe(
      JSON.stringify({ email: 'admin@example.com', password: 'a-long-password' }),
    );
  });

  it('rejects a session payload that does not match the contract', async () => {
    stubFetch({ body: { ...session, role: 'superuser' } });

    await expect(httpAuthService.session()).rejects.toMatchObject({ code: 'invalid_response' });
  });
});

describe('csrf token', () => {
  it('echoes the readable cookie on state-changing requests', async () => {
    document.cookie = 'agenthub_csrf=token-from-cookie; path=/';
    const fetchMock = stubFetch({ status: 204 });

    await apiRequestVoid('/api/v1/auth/logout', { method: 'POST' });

    expect(headerOf(requestOf(fetchMock).init, 'X-CSRF-Token')).toBe('token-from-cookie');
  });

  it('does not send it on reads', async () => {
    document.cookie = 'agenthub_csrf=token-from-cookie; path=/';
    const fetchMock = stubFetch({ body: session });

    await httpAuthService.session();

    expect(headerOf(requestOf(fetchMock).init, 'X-CSRF-Token')).toBeUndefined();
  });

  it('sends nothing when there is no cookie to read', async () => {
    const fetchMock = stubFetch({ status: 204 });

    await apiRequestVoid('/api/v1/auth/logout', { method: 'POST' });

    expect(headerOf(requestOf(fetchMock).init, 'X-CSRF-Token')).toBeUndefined();
  });
});

describe('members', () => {
  it('lists the organization members', async () => {
    const fetchMock = stubFetch({ body: { items: [member], total: 1, limit: 200, offset: 0 } });

    await expect(httpMemberService.list()).resolves.toEqual([member]);
    expect(requestOf(fetchMock).url).toContain('/api/v1/members');
  });

  it('adds, re-roles and removes by id', async () => {
    const fetchMock = stubFetch({ body: member }, { body: member }, { status: 204 });

    await httpMemberService.add('someone@example.com', 'viewer');
    await httpMemberService.setRole('mem_1', 'admin');
    await httpMemberService.remove('mem_1');

    expect(requestOf(fetchMock, 0).init.body).toBe(
      JSON.stringify({ email: 'someone@example.com', role: 'viewer' }),
    );
    expect(requestOf(fetchMock, 1).init.method).toBe('PATCH');
    expect(requestOf(fetchMock, 2).init.method).toBe('DELETE');
    expect(requestOf(fetchMock, 2).url).toBe('/api/v1/members/mem_1');
  });
});
