import { DemoBadge } from '@/components/feedback/DemoNotice';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { ComponentStateBadge } from '@/components/status/StatusBadges';
import { Card, CardHeader } from '@/components/ui/Card';
import { useComponentStatus } from '../api';

export function SystemStatusCard() {
  const query = useComponentStatus();
  return (
    <Card>
      <CardHeader title="System status" description="Simulated states for demonstration." action={<DemoBadge />} />
      <div className="p-4">
        <QueryState query={query} loading={<LoadingState variant="inline" label="Loading system status…" />} errorTitle="Status unavailable">
          {(components) => (
            <ul className="divide-y divide-line">
              {components.map((component) => (
                <li key={component.id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-fg">{component.name}</p>
                    <p className="text-xs text-fg-muted">{component.detail}</p>
                  </div>
                  <ComponentStateBadge state={component.state} />
                </li>
              ))}
            </ul>
          )}
        </QueryState>
        <p className="mt-4 text-xs text-fg-subtle">
          These are not real health checks. Live service health will be reported once the backend services exist.
        </p>
      </div>
    </Card>
  );
}
