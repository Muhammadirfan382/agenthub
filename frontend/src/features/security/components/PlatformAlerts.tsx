import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { usePermission } from '@/features/auth/api';
import { formatRelative } from '@/lib/format';
import type { AlertRecord } from '@/types/domain';
import { useResolveAlert } from '../api';

const TONES: Record<AlertRecord['severity'], 'info' | 'warning' | 'danger'> = {
  info: 'info',
  warning: 'warning',
  critical: 'danger',
};

const LABELS: Record<AlertRecord['severity'], string> = {
  info: 'Info',
  warning: 'Warning',
  critical: 'Critical',
};

/** Alerts the backend raised from its own rules; administrators can close them. */
export function PlatformAlerts({ alerts }: { alerts: AlertRecord[] }) {
  const permitted = usePermission();
  const resolve = useResolveAlert();
  const canResolve = permitted('runtime:pause');

  if (alerts.length === 0) {
    return <Alert tone="success" title="No alerts firing" />;
  }
  return (
    <ul className="space-y-3">
      {alerts.map((alert) => (
        <li key={alert.id}>
          <Alert
            tone={TONES[alert.severity]}
            title={`${LABELS[alert.severity]}: ${alert.summary}`}
            action={
              canResolve ? (
                <Button
                  size="sm"
                  variant="ghost"
                  loading={resolve.isPending && resolve.variables === alert.id}
                  onClick={() => resolve.mutate(alert.id)}
                >
                  Resolve
                </Button>
              ) : undefined
            }
          >
            First seen {formatRelative(alert.firstSeen)} · last seen {formatRelative(alert.lastSeen)}
            {alert.occurrences > 1 ? ` · seen ${alert.occurrences} times` : ''}
          </Alert>
        </li>
      ))}
      {resolve.isError && (
        <li>
          <Alert tone="danger" title="The alert could not be resolved">
            {resolve.error.message}
          </Alert>
        </li>
      )}
    </ul>
  );
}
