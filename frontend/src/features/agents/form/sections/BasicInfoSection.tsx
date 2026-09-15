import { useFormContext } from 'react-hook-form';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { FormSection } from '../FormSection';
import type { AgentFormInput } from '../schema';

export function BasicInfoSection({ step }: { step: number }) {
  const { register, formState } = useFormContext<AgentFormInput>();
  const { errors } = formState;
  return (
    <FormSection id="basic" step={step} title="Basic information" description="How the agent is identified in your workspace.">
      <div className="grid gap-5 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Field label="Agent name" required hint="3–60 characters." error={errors.name?.message}>
          {(control) => <Input {...control} {...register('name')} autoComplete="off" placeholder="e.g. Research Scout" />}
        </Field>
        <Field label="Version" required hint="Semantic version, e.g. 1.0.0." error={errors.version?.message}>
          {(control) => <Input {...control} {...register('version')} autoComplete="off" className="font-mono" />}
        </Field>
      </div>
    </FormSection>
  );
}
