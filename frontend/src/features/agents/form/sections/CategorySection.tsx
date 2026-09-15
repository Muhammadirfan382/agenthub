import { useFormContext } from 'react-hook-form';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { AGENT_CATEGORIES } from '@/types/domain';
import { FormSection } from '../FormSection';
import type { AgentFormInput } from '../schema';

export function CategorySection({ step }: { step: number }) {
  const { register, formState } = useFormContext<AgentFormInput>();
  return (
    <FormSection id="category" step={step} title="Category" description="Used for filtering and marketplace discovery.">
      <Field label="Category" required error={formState.errors.category?.message} className="sm:max-w-sm">
        {(control) => (
          <Select {...control} {...register('category')}>
            <option value="">Select a category</option>
            {AGENT_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {CATEGORY_LABELS[category]}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </FormSection>
  );
}
