import { Database, Server } from 'lucide-react';
import { useId } from 'react';
import { appConfig } from '@/config/env';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { cn } from '@/lib/cn';
import type { DataSource } from '@/services/contracts';
import { useServices } from '@/services/ServicesContext';
import { useDataSourceStore } from '@/stores/dataSourceStore';
import { useBackendHealthCheck } from '../api';

const DATA_SOURCES: { value: DataSource; label: string; description: string; icon: typeof Server }[] = [
  { value: 'demo', label: 'Demo data', description: 'Sample data held in memory. No backend needed.', icon: Database },
  { value: 'api', label: 'Backend API', description: 'Real agents and executions from the AgentHub API.', icon: Server },
];

/** Masked placeholder. It is not, and must never become, a real key. */
const API_KEY_PLACEHOLDER = '••••••••••••••••••••••••';

export function ApiSettings() {
  const health = useBackendHealthCheck();
  const { dataSource, liveResources } = useServices();
  const setDataSource = useDataSourceStore((state) => state.setDataSource);
  const keyId = useId();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Data source" description="Where the app reads its data. Remembered in this browser." />
        <CardBody className="space-y-4">
          <fieldset>
            <legend className="text-sm font-medium text-fg">Mode</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {DATA_SOURCES.map(({ value, label, description, icon: Icon }) => (
                <label
                  key={value}
                  className={cn(
                    'flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring',
                    dataSource === value ? 'border-brand bg-brand-soft text-brand-strong' : 'border-line text-fg hover:bg-surface-hover',
                  )}
                >
                  <input
                    type="radio"
                    name="data-source"
                    value={value}
                    checked={dataSource === value}
                    onChange={() => setDataSource(value)}
                    className="sr-only"
                  />
                  <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  <span>
                    <span className="block font-medium">{label}</span>
                    <span className="block text-xs text-fg-muted">{description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          {dataSource === 'api' ? (
            <Alert tone="warning" title="Partly live">
              The backend serves {liveResources.join(', ')}. Marketplace, security, analytics and profile data are still
              demonstration data. Start the API on 127.0.0.1:8000 first, or requests will fail.
            </Alert>
          ) : (
            <Alert tone="info" title="Nothing leaves the browser">
              Demo data is generated in memory and resets on reload. Switch to the backend API to store agents for real.
            </Alert>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Backend connection" description="Liveness check against GET /api/v1/health." />
        <CardBody className="space-y-4">
          <dl className="text-sm">
            <dt className="text-xs text-fg-subtle">API base URL (VITE_API_BASE_URL)</dt>
            <dd className="mt-0.5 font-mono text-fg">{appConfig.apiBaseUrl || 'Same origin (development proxy to 127.0.0.1:8000)'}</dd>
          </dl>
          <Button variant="secondary" onClick={() => health.mutate()} loading={health.isPending}>
            Test connection
          </Button>
          <div aria-live="polite">
            {health.isSuccess && (
              <Alert tone="success" title="Backend reachable">
                {health.data.service} v{health.data.version}: {health.data.message}
              </Alert>
            )}
            {health.isError && (
              <Alert tone="danger" title="Backend unreachable">
                Start the backend on http://127.0.0.1:8000 and try again.
              </Alert>
            )}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="API keys" description="Programmatic access is not available yet." />
        <CardBody className="space-y-3">
          <label htmlFor={keyId} className="text-sm font-medium text-fg">
            Workspace API key (demo placeholder)
          </label>
          <input
            id={keyId}
            type="text"
            readOnly
            disabled
            value={API_KEY_PLACEHOLDER}
            aria-describedby={`${keyId}-hint`}
            className="h-9 w-full rounded-md border border-line bg-surface-muted px-3 font-mono text-sm text-fg-muted"
          />
          <p id={`${keyId}-hint`} className="text-xs text-fg-muted">
            No key exists. Real keys will be generated by the backend, shown once, and never stored in the frontend.
          </p>
          <Button variant="secondary" disabled>
            Generate API key
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}
