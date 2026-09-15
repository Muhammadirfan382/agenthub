import { useFormContext } from 'react-hook-form';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { FormSection } from '../FormSection';
import { type AgentFormInput, MODEL_OPTIONS } from '../schema';

export function ModelSection({ step }: { step: number }) {
  const { register, formState } = useFormContext<AgentFormInput>();
  const errors = formState.errors.model;
  return (
    <FormSection
      id="model"
      step={step}
      title="Model configuration"
      description="Model tiers are routed through the future model gateway. No provider is connected and no API key is needed here."
    >
      <div className="grid gap-5 sm:grid-cols-3">
        <Field label="Model" required error={errors?.model?.message}>
          {(control) => (
            <Select {...control} {...register('model.model')}>
              {MODEL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Temperature" required hint="0 (deterministic) to 2." error={errors?.temperature?.message}>
          {(control) => <Input {...control} {...register('model.temperature', { valueAsNumber: true })} type="number" step="0.1" min={0} max={2} inputMode="decimal" />}
        </Field>
        <Field label="Max output tokens" required hint="256 to 32,000." error={errors?.maxOutputTokens?.message}>
          {(control) => <Input {...control} {...register('model.maxOutputTokens', { valueAsNumber: true })} type="number" step={1} min={256} max={32000} inputMode="numeric" />}
        </Field>
      </div>
    </FormSection>
  );
}
