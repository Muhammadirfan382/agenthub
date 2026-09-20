import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { contentSecurityPolicy } from '@/config/contentSecurityPolicy';
import { renderApp, servicesAs, testServices } from '@/test/renderApp';
import type { AuditEvent, ExecutionDetail } from '@/types/domain';

const EVENTS: AuditEvent[] = [
  {
    id: 'aud_1',
    at: '2026-09-18T10:00:00.000Z',
    actorType: 'agent',
    actorId: 'agt_1',
    actorName: 'Status Checker',
    action: 'policy.denied',
    targetType: 'execution',
    targetId: 'exe_1',
    outcome: 'denied',
    detail: { tool: 'api_request', rule: 'egress.not_allowed' },
  },
  {
    id: 'aud_2',
    at: '2026-09-18T09:00:00.000Z',
    actorType: 'user',
    actorId: 'usr_1',
    actorName: 'Admin Person',
    action: 'auth.login',
    targetType: 'user',
    targetId: 'usr_1',
    outcome: 'success',
    detail: {},
  },
];

describe('the content security policy', () => {
  it('allows only the application itself', () => {
    const policy = contentSecurityPolicy(undefined);

    expect(policy).toContain("script-src 'self'");
    expect(policy).toContain("style-src 'self'");
    expect(policy).toContain("object-src 'none'");
    expect(policy).toContain("connect-src 'self'");
    expect(policy).not.toContain('unsafe-inline');
    expect(policy).not.toContain('unsafe-eval');
  });

  it('adds only the origin of a separately hosted API', () => {
    const policy = contentSecurityPolicy('https://api.agenthub.example/some/path');

    expect(policy).toContain("connect-src 'self' https://api.agenthub.example;");
    expect(policy).not.toContain('/some/path');
  });

  it('refuses an API address that is not http(s)', () => {
    expect(() => contentSecurityPolicy('javascript:alert(1)')).toThrow();
  });
});

describe('the audit log', () => {
  it('shows administrators what was recorded', async () => {
    const services = servicesAs('admin');
    renderApp('/settings?section=audit', {
      ...services,
      audit: { list: () => Promise.resolve(EVENTS) },
    });

    const table = await screen.findByRole('table', { name: 'Audit events' });
    expect(within(table).getByText('policy.denied')).toBeInTheDocument();
    expect(within(table).getByText(/rule: egress.not_allowed/)).toBeInTheDocument();
    expect(within(table).getByText('Status Checker')).toBeInTheDocument();
  });

  it('asks the server for the chosen area and outcome', async () => {
    const services = servicesAs('admin');
    const list = vi.fn(() => Promise.resolve(EVENTS));
    const { user } = renderApp('/settings?section=audit', {
      ...services,
      audit: { list },
    });

    await screen.findByRole('table', { name: 'Audit events' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Area' }), 'egress.');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Outcome' }), 'denied');

    await vi.waitFor(() =>
      expect(list).toHaveBeenLastCalledWith({ action: 'egress.', outcome: 'denied' }),
    );
  });

  it('is not even requested for roles that may not read it', async () => {
    const services = servicesAs('member');
    const list = vi.fn(() => Promise.resolve(EVENTS));
    renderApp('/settings?section=audit', { ...services, audit: { list } });

    expect(await screen.findByText('Only administrators can read the audit log')).toBeInTheDocument();
    expect(list).not.toHaveBeenCalled();
  });

  it('is empty in demo mode rather than invented', async () => {
    renderApp('/settings?section=audit', servicesAs('admin'));

    expect(await screen.findByText('Nothing recorded')).toBeInTheDocument();
  });
});

describe('a tool that ran', () => {
  it('is labelled as a GET that ran, not merely as success', async () => {
    const base = testServices();
    const services = {
      ...base,
      executions: {
        ...base.executions,
        async get(id: string) {
          const detail = await base.executions.get(id);
          if (!detail) return detail;
          const ran: ExecutionDetail = {
            ...detail,
            toolCalls: [
              {
                id: 'tcl_1',
                tool: 'api_request',
                capability: 'api_access',
                status: 'succeeded',
                startedAt: detail.startedAt,
                durationMs: 120,
                inputSummary: '{"method": "GET", "url": "https://api.example.com/status"}',
                outputSummary: '200 application/json, 16 bytes',
              },
            ],
          };
          return ran;
        },
      },
    };
    renderApp('/executions/exe_a4c6e210', services);

    expect(await screen.findByText('Ran (GET)')).toBeInTheDocument();
  });
});
