import { useEffect, useState } from 'react';
import { fetchBackendHealth, type BackendHealth } from '../api/health';

type BackendState =
  | { kind: 'checking' }
  | { kind: 'online'; health: BackendHealth }
  | { kind: 'unreachable' };

const HEALTH_TIMEOUT_MS = 5000;

export function StatusPage() {
  const [backend, setBackend] = useState<BackendState>({ kind: 'checking' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

    fetchBackendHealth(controller.signal)
      .then((health) => {
        if (!cancelled) setBackend({ kind: 'online', health });
      })
      .catch(() => {
        // Covers network errors, timeouts, non-2xx responses and unexpected
        // payloads. Details are deliberately not shown to the user.
        if (!cancelled) setBackend({ kind: 'unreachable' });
      })
      .finally(() => window.clearTimeout(timeout));

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  const checkAgain = () => {
    setBackend({ kind: 'checking' });
    setAttempt((current) => current + 1);
  };

  return (
    <main className="page">
      <header className="page-header">
        <h1>AgentHub</h1>
        <p className="notice">AgentHub is currently under active development.</p>
      </header>

      <section className="card" aria-labelledby="status-heading">
        <h2 id="status-heading">Development status</h2>

        <dl className="status-list">
          <div className="status-row">
            <dt>Phase</dt>
            <dd>Phase 0: Project initialization</dd>
          </div>
          <div className="status-row">
            <dt>Frontend</dt>
            <dd>
              <span className="badge badge-ok">Running</span>
            </dd>
          </div>
          <div className="status-row">
            <dt>Backend API</dt>
            <dd role="status" aria-live="polite">
              <BackendStatus state={backend} />
            </dd>
          </div>
        </dl>

        <button type="button" onClick={checkAgain} disabled={backend.kind === 'checking'}>
          Check again
        </button>
      </section>

      <p className="footnote">
        This page only reports service health. No product features are implemented yet.
      </p>
    </main>
  );
}

function BackendStatus({ state }: { state: BackendState }) {
  switch (state.kind) {
    case 'checking':
      return <span className="badge badge-pending">Checking…</span>;
    case 'online':
      return (
        <>
          <span className="badge badge-ok">Online</span>{' '}
          <span className="detail">
            {state.health.service} v{state.health.version}
          </span>
        </>
      );
    case 'unreachable':
      return (
        <>
          <span className="badge badge-error">Unreachable</span>{' '}
          <span className="detail">Start the backend on http://127.0.0.1:8000</span>
        </>
      );
  }
}
