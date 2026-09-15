import { Alert } from '@/components/ui/Alert';
import { PermissionIndicator } from '@/components/status/PermissionIndicator';
import type { Agent } from '@/types/domain';

export function AgentCapabilitiesTab({ agent }: { agent: Agent }) {
  const granted = agent.permissions.filter((p) => p.level !== 'denied');
  const denied = agent.permissions.filter((p) => p.level === 'denied');

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Permission indicators describe configuration, not enforcement">
        The frontend only displays what this agent requests. Permissions will be enforced server-side by the backend and
        tool gateway in later phases; nothing shown here is a security control.
      </Alert>

      <section aria-labelledby="granted-heading">
        <h2 id="granted-heading" className="mb-3 text-sm font-semibold text-fg">
          Permitted capabilities ({granted.length})
        </h2>
        {granted.length === 0 ? (
          <p className="text-sm text-fg-muted">This agent requests no capabilities.</p>
        ) : (
          <ul className="space-y-2">
            {granted.map((permission) => (
              <PermissionIndicator key={permission.capability} permission={permission} />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="denied-heading">
        <h2 id="denied-heading" className="mb-3 text-sm font-semibold text-fg">
          Not permitted ({denied.length})
        </h2>
        <ul className="grid gap-2 md:grid-cols-2">
          {denied.map((permission) => (
            <PermissionIndicator key={permission.capability} permission={permission} />
          ))}
        </ul>
      </section>
    </div>
  );
}
