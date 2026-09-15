import { useFormContext, useWatch } from 'react-hook-form';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CAPABILITY_META } from '@/components/status/meta';
import { Alert } from '@/components/ui/Alert';
import { Checkbox } from '@/components/ui/Checkbox';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { FormSection } from '../FormSection';
import { type AgentFormInput, permissionRisk } from '../schema';

export function PermissionsSection({ step }: { step: number }) {
  const { register, control, formState } = useFormContext<AgentFormInput>();
  const permissions = useWatch({ control, name: 'permissions' });

  return (
    <FormSection
      id="permissions"
      step={step}
      title="Permissions"
      description="Deny by default. Grant only what the agent needs and scope it as narrowly as possible."
    >
      <Alert tone="info" title="The frontend does not enforce permissions">
        These settings describe the requested configuration. Enforcement will happen server-side in later phases.
      </Alert>
      <ul className="space-y-3">
        {permissions.map((permission, index) => {
          const meta = CAPABILITY_META[permission.capability];
          const Icon = meta.icon;
          const denied = permission.level === 'denied';
          const errors = formState.errors.permissions?.[index];
          const scopeId = `permission-${permission.capability}-scope`;
          return (
            <li key={permission.capability} className="rounded-lg border border-line p-4">
              <div className="flex flex-wrap items-start gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-md bg-surface-muted text-fg-muted">
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-fg">{meta.label}</p>
                  <p className="text-xs text-fg-muted">{meta.description}</p>
                </div>
                {denied ? (
                  <span className="text-xs text-fg-subtle">Not granted</span>
                ) : (
                  <RiskBadge level={permissionRisk(permission.capability, permission.level)} />
                )}
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-[10rem_minmax(0,1fr)]">
                <Select aria-label={`Access level for ${meta.label}`} {...register(`permissions.${index}.level`)}>
                  <option value="denied">Denied</option>
                  <option value="read_only">Read only</option>
                  <option value="restricted">Restricted</option>
                  <option value="allowed">Allowed</option>
                </Select>
                <div>
                  <Input
                    id={scopeId}
                    aria-label={`Scope for ${meta.label}`}
                    placeholder={denied ? 'Grant access to set a scope' : 'e.g. Allow-listed domains only'}
                    disabled={denied}
                    aria-invalid={errors?.scope ? true : undefined}
                    aria-describedby={errors?.scope ? `${scopeId}-error` : undefined}
                    {...register(`permissions.${index}.scope`)}
                  />
                  {errors?.scope?.message && (
                    <p id={`${scopeId}-error`} className="mt-1 text-xs font-medium text-danger">
                      {errors.scope.message}
                    </p>
                  )}
                </div>
              </div>
              <Checkbox
                className="mt-3"
                disabled={denied}
                label="Require human approval before each use"
                aria-invalid={errors?.requiresApproval ? true : undefined}
                {...register(`permissions.${index}.requiresApproval`)}
              />
              {errors?.requiresApproval?.message && <p className="mt-1 text-xs font-medium text-danger">{errors.requiresApproval.message}</p>}
            </li>
          );
        })}
      </ul>
    </FormSection>
  );
}
