import { useFormContext } from 'react-hook-form';
import { CAPABILITY_META } from '@/components/status/meta';
import { Checkbox } from '@/components/ui/Checkbox';
import { FormSection } from '../FormSection';
import { type AgentFormInput, TOOL_OPTIONS } from '../schema';

export function ToolsSection({ step }: { step: number }) {
  const { register, formState } = useFormContext<AgentFormInput>();
  const error = formState.errors.tools?.message ?? formState.errors.tools?.root?.message;
  return (
    <FormSection id="tools" step={step} title="Tools" description="Each tool requires a matching capability in Permissions.">
      <div role="group" aria-labelledby="tools-group-label" aria-describedby={error ? 'tools-error' : undefined} className="space-y-3">
        <p id="tools-group-label" className="sr-only">
          Tools
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {TOOL_OPTIONS.map((tool) => (
            <Checkbox
              key={tool.id}
              value={tool.id}
              {...register('tools')}
              label={tool.label}
              description={`Needs: ${CAPABILITY_META[tool.capability].label}`}
              className="rounded-md border border-line p-3"
            />
          ))}
        </div>
        {error && (
          <p id="tools-error" className="text-xs font-medium text-danger">
            {error}
          </p>
        )}
      </div>
    </FormSection>
  );
}
