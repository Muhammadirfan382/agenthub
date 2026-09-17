import { useState } from 'react';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CAPABILITY_META, PERMISSION_LEVEL_META } from '@/components/status/meta';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { permissionRisk } from '@/lib/risk';
import type { AgentPermission, CapabilityKey, PermissionLevel } from '@/types/domain';
import type { GrantDraft, GrantState } from '../grants';

const LEVEL_ORDER: PermissionLevel[] = ['denied', 'read_only', 'restricted', 'allowed'];

interface GrantEditorProps {
  /** What the manifest asks for. Capabilities it denies cannot be granted. */
  requested: AgentPermission[];
  value: GrantState;
  onChange: (next: GrantState) => void;
  disabled?: boolean;
}

/**
 * The install decision, made visible: what was asked for on the left, what you
 * are granting on the right. A grant can never exceed the request, which the
 * backend enforces again on submit.
 */
export function GrantEditor({ requested, value, onChange, disabled = false }: GrantEditorProps) {
  const [touched, setTouched] = useState(false);
  const asked = requested.filter((permission) => permission.level !== 'denied');

  if (asked.length === 0) {
    return (
      <Alert tone="success" title="This agent asks for no permissions">
        Nothing to grant. It can still be installed and updated later.
      </Alert>
    );
  }

  const update = (capability: CapabilityKey, patch: Partial<GrantDraft>) => {
    setTouched(true);
    const current = value[capability] ?? { level: 'denied' as PermissionLevel, scope: '', requiresApproval: false };
    const next: GrantState = { ...value, [capability]: { ...current, ...patch } };
    onChange(next);
  };

  return (
    <div className="space-y-4">
      {asked.map((permission) => {
        const meta = CAPABILITY_META[permission.capability];
        const draft = value[permission.capability];
        const level = draft?.level ?? 'denied';
        // Never offer more than the publisher asked for.
        const options = LEVEL_ORDER.slice(0, LEVEL_ORDER.indexOf(permission.level) + 1);
        const risk = permissionRisk(permission.capability, level);
        const approvalForced = permission.requiresApproval || risk === 'critical';
        const missingScope = touched && level !== 'denied' && draft!.scope.trim().length < 3;

        return (
          <div key={permission.capability} className="rounded-lg border border-line p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-medium text-fg">
                  <meta.icon aria-hidden="true" className="size-4 text-fg-subtle" />
                  {meta.label}
                </p>
                <p className="mt-0.5 text-xs text-fg-muted">{meta.description}</p>
                <p className="mt-1 text-xs text-fg-subtle">
                  Asked for: <strong className="font-medium text-fg-muted">{PERMISSION_LEVEL_META[permission.level].label}</strong>
                  {permission.scope ? ` — ${permission.scope}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {permission.requiresApproval && <Badge tone="warning">Approval required</Badge>}
                <RiskBadge level={risk} />
              </div>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-[10rem_minmax(0,1fr)]">
              <Select
                aria-label={`Grant level for ${meta.label}`}
                value={level}
                disabled={disabled}
                onChange={(event) =>
                  update(permission.capability, { level: event.target.value as PermissionLevel })
                }
              >
                {options.map((option) => (
                  <option key={option} value={option}>
                    {option === 'denied' ? 'Not granted' : PERMISSION_LEVEL_META[option].label}
                  </option>
                ))}
              </Select>
              <Input
                aria-label={`Scope for ${meta.label}`}
                placeholder="What exactly may it reach? For example: the shared research folder"
                value={draft?.scope ?? ''}
                disabled={disabled || level === 'denied'}
                aria-invalid={missingScope ? true : undefined}
                onChange={(event) => update(permission.capability, { scope: event.target.value })}
              />
            </div>
            {missingScope && (
              <p className="mt-1.5 text-xs text-danger">
                Describe the scope you are granting, so the limit is on the record.
              </p>
            )}

            {level !== 'denied' && (
              <Switch
                className="mt-3"
                label="Require human approval before it acts"
                description={
                  approvalForced
                    ? 'Required for this grant and cannot be turned off.'
                    : 'Each use waits for a person to approve it.'
                }
                checked={approvalForced || (draft?.requiresApproval ?? false)}
                disabled={disabled || approvalForced}
                onCheckedChange={(checked) =>
                  update(permission.capability, { requiresApproval: checked })
                }
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
