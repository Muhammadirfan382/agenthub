import { KeyRound, Monitor } from 'lucide-react';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export function SecuritySettings() {
  return (
    <div className="space-y-6">
      <Alert tone="warning" title="Authentication is not implemented yet">
        There are no real accounts, passwords, sessions or MFA in this build. The frontend never acts as a security
        control; sign-in and authorization will be enforced by the backend in Phase 3.
      </Alert>
      <Card>
        <CardHeader title="Multi-factor authentication" />
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <KeyRound aria-hidden="true" className="size-5 text-fg-subtle" />
            <div>
              <p className="text-sm font-medium text-fg">Authenticator app or passkey</p>
              <p className="text-xs text-fg-muted">Available once authentication exists.</p>
            </div>
          </div>
          <Button variant="secondary" disabled>
            Set up MFA
          </Button>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Active sessions" />
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Monitor aria-hidden="true" className="size-5 text-fg-subtle" />
            <div>
              <p className="text-sm font-medium text-fg">This browser</p>
              <p className="text-xs text-fg-muted">Demo session, not a real authenticated session.</p>
            </div>
          </div>
          <Badge tone="info">Demo</Badge>
        </CardBody>
      </Card>
    </div>
  );
}
