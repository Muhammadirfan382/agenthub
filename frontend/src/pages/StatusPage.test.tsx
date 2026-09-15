import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import { HEALTH_ENDPOINT } from '../api/health';

function stubFetch(implementation: () => Promise<unknown>) {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

describe('AgentHub status page', () => {
  it('starts up and shows the development notice', () => {
    stubFetch(() => new Promise(() => {}));

    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: 'AgentHub' })).toBeInTheDocument();
    expect(screen.getByText('AgentHub is currently under active development.')).toBeInTheDocument();
    expect(screen.getByText('Checking…')).toBeInTheDocument();
  });

  it('shows the backend as online when the health endpoint responds', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse({
        status: 'ok',
        service: 'agenthub-backend',
        version: '0.1.0',
        message: 'AgentHub backend is running.',
      }),
    );

    render(<App />);

    expect(await screen.findByText('Online')).toBeInTheDocument();
    expect(screen.getByText('agenthub-backend v0.1.0')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(HEALTH_ENDPOINT, expect.objectContaining({ method: 'GET' }));
  });

  it('shows the backend as unreachable when the request fails', async () => {
    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')));

    render(<App />);

    expect(await screen.findByText('Unreachable')).toBeInTheDocument();
  });

  it('treats an unexpected health payload as unreachable', async () => {
    stubFetch(() => jsonResponse({ status: 'maybe' }));

    render(<App />);

    expect(await screen.findByText('Unreachable')).toBeInTheDocument();
  });

  it('treats a non-2xx response as unreachable', async () => {
    stubFetch(() => jsonResponse({ status: 'ok' }, 503));

    render(<App />);

    expect(await screen.findByText('Unreachable')).toBeInTheDocument();
  });
});
