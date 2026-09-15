import { useFormContext, useWatch } from 'react-hook-form';
import { Field } from '@/components/ui/Field';
import { Textarea } from '@/components/ui/Textarea';
import { FormSection } from '../FormSection';
import type { AgentFormInput } from '../schema';

const MAX = 500;

export function DescriptionSection({ step }: { step: number }) {
  const { register, formState, control } = useFormContext<AgentFormInput>();
  const description = useWatch({ control, name: 'description' });
  return (
    <FormSection id="description" step={step} title="Description" description="Explain what the agent does and what it must never do.">
      <Field
        label="Description"
        required
        hint={`${description.length}/${MAX} characters (minimum 20).`}
        error={formState.errors.description?.message}
      >
        {(fieldControl) => <Textarea {...fieldControl} {...register('description')} rows={5} maxLength={MAX} />}
      </Field>
    </FormSection>
  );
}
