import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Switch } from '@/components/ui/Switch';
import { toast } from '@/stores/toastStore';

const OPTIONS = [
  { id: 'executionFailures', label: 'Execution failures', description: 'When an execution fails or times out.' },
  { id: 'securityAlerts', label: 'Security alerts', description: 'High and critical security events.' },
  { id: 'approvalRequests', label: 'Approval requests', description: 'When an agent is waiting for a human decision.' },
  { id: 'weeklySummary', label: 'Weekly summary', description: 'A digest of agent activity.' },
] as const;

type Preferences = Record<(typeof OPTIONS)[number]['id'], boolean>;

export function NotificationSettings() {
  const [preferences, setPreferences] = useState<Preferences>({
    executionFailures: true,
    securityAlerts: true,
    approvalRequests: true,
    weeklySummary: false,
  });

  return (
    <Card>
      <CardHeader title="Notifications" description="No notifications are delivered yet; preferences are not saved." />
      <CardBody className="space-y-5">
        {OPTIONS.map((option) => (
          <Switch
            key={option.id}
            label={option.label}
            description={option.description}
            checked={preferences[option.id]}
            onCheckedChange={(checked) => setPreferences((current) => ({ ...current, [option.id]: checked }))}
          />
        ))}
        <div className="flex justify-end">
          <Button onClick={() => toast.info('Preferences not saved', 'Notification delivery is not implemented yet.')}>Save preferences</Button>
        </div>
      </CardBody>
    </Card>
  );
}
