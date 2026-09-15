import { useFormContext, useWatch } from 'react-hook-form';
import { RISK_META } from '@/components/status/meta';
import { Checkbox } from '@/components/ui/Checkbox';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { RISK_LEVELS } from '@/types/domain';
import { FormSection } from '../FormSection';
import type { AgentFormInput } from '../schema';

export function SecurityPolicySection({ step }: { step: number }) {
  const { register, control, formState } = useFormContext<AgentFormInput>();
  const egress = useWatch({ control, name: 'securityPolicy.networkEgress' });
  const errors = formState.errors.securityPolicy;

  return (
    <FormSection id="security" step={step} title="Security policy" description="Isolation, network and approval rules for this agent.">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Sandbox" required hint="Strict isolation is required for code execution." error={errors?.sandbox?.message}>
          {(fieldControl) => (
            <Select {...fieldControl} {...register('securityPolicy.sandbox')}>
              <option value="strict">Strict</option>
              <option value="standard">Standard</option>
            </Select>
          )}
        </Field>
        <Field label="Network egress" required error={errors?.networkEgress?.message}>
          {(fieldControl) => (
            <Select {...fieldControl} {...register('securityPolicy.networkEgress')}>
              <option value="none">None (no network access)</option>
              <option value="allow_list">Allow-list only</option>
            </Select>
          )}
        </Field>
      </div>

      {egress === 'allow_list' && (
        <Field label="Allowed domains" required hint="One hostname per line, e.g. docs.example.com. No schemes, paths or wildcards." error={errors?.allowedDomainsText?.message}>
          {(fieldControl) => <Textarea {...fieldControl} {...register('securityPolicy.allowedDomainsText')} rows={3} className="font-mono" spellCheck={false} />}
        </Field>
      )}

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-fg">Require approval for actions at these risk levels</legend>
        <div className="flex flex-wrap gap-4">
          {RISK_LEVELS.map((level) => (
            <Checkbox key={level} value={level} label={RISK_META[level].label} {...register('securityPolicy.approvalRequiredFor')} />
          ))}
        </div>
      </fieldset>

      <div>
        <Checkbox
          label="Audit logging"
          description="Record every tool call and decision. Required when high-risk capabilities are granted."
          aria-invalid={errors?.auditLogging ? true : undefined}
          {...register('securityPolicy.auditLogging')}
        />
        {errors?.auditLogging?.message && <p className="mt-1 text-xs font-medium text-danger">{errors.auditLogging.message}</p>}
      </div>
    </FormSection>
  );
}
