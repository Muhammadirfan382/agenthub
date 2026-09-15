import { useFormContext } from 'react-hook-form';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { FormSection } from '../FormSection';
import type { AgentFormInput } from '../schema';

const LIMITS = [
  { name: 'maxRuntimeSeconds', label: 'Max runtime (seconds)', hint: '10 to 3,600.', min: 10, max: 3600 },
  { name: 'maxMemoryMb', label: 'Max memory (MB)', hint: '128 to 8,192.', min: 128, max: 8192 },
  { name: 'maxTokensPerRun', label: 'Max tokens per run', hint: '1,000 to 200,000.', min: 1000, max: 200000 },
  { name: 'maxToolCalls', label: 'Max tool calls', hint: '0 to 500.', min: 0, max: 500 },
] as const;

export function ResourceLimitsSection({ step }: { step: number }) {
  const { register, formState } = useFormContext<AgentFormInput>();
  return (
    <FormSection id="limits" step={step} title="Resource limits" description="Hard ceilings the future runtime will enforce per execution.">
      <div className="grid gap-5 sm:grid-cols-2">
        {LIMITS.map((limit) => (
          <Field key={limit.name} label={limit.label} required hint={limit.hint} error={formState.errors.resourceLimits?.[limit.name]?.message}>
            {(control) => (
              <Input
                {...control}
                {...register(`resourceLimits.${limit.name}`, { valueAsNumber: true })}
                type="number"
                step={1}
                min={limit.min}
                max={limit.max}
                inputMode="numeric"
              />
            )}
          </Field>
        ))}
      </div>
    </FormSection>
  );
}
