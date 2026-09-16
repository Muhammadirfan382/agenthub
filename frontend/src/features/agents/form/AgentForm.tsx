import { zodResolver } from '@hookform/resolvers/zod';
import { FormProvider, type SubmitErrorHandler, useForm } from 'react-hook-form';
import { useState } from 'react';
import { Alert } from '@/components/ui/Alert';
import { Button, LinkButton } from '@/components/ui/Button';
import { type AgentFormInput, type AgentFormValues, agentFormSchema } from './schema';
import { BasicInfoSection } from './sections/BasicInfoSection';
import { CategorySection } from './sections/CategorySection';
import { DescriptionSection } from './sections/DescriptionSection';
import { ModelSection } from './sections/ModelSection';
import { PermissionsSection } from './sections/PermissionsSection';
import { ResourceLimitsSection } from './sections/ResourceLimitsSection';
import { ReviewSection } from './sections/ReviewSection';
import { SecurityPolicySection } from './sections/SecurityPolicySection';
import { TagsSection } from './sections/TagsSection';
import { ToolsSection } from './sections/ToolsSection';

const FORM_SECTIONS = [
  { id: 'basic', title: 'Basic information' },
  { id: 'description', title: 'Description' },
  { id: 'category', title: 'Category' },
  { id: 'tags', title: 'Tags' },
  { id: 'model', title: 'Model configuration' },
  { id: 'tools', title: 'Tools' },
  { id: 'permissions', title: 'Permissions' },
  { id: 'limits', title: 'Resource limits' },
  { id: 'security', title: 'Security policy' },
  { id: 'review', title: 'Review' },
] as const;

interface AgentFormProps {
  defaultValues: AgentFormInput;
  submitLabel: string;
  cancelTo: string;
  submitting: boolean;
  /** Set when the signed-in role may not save: the form stays readable but inert. */
  disabled?: boolean;
  onSubmit: (values: AgentFormValues) => void;
}

export function AgentForm({
  defaultValues,
  submitLabel,
  cancelTo,
  submitting,
  disabled = false,
  onSubmit,
}: AgentFormProps) {
  const form = useForm<AgentFormInput, unknown, AgentFormValues>({
    resolver: zodResolver(agentFormSchema),
    defaultValues,
    mode: 'onTouched',
  });
  const [errorCount, setErrorCount] = useState(0);

  const onInvalid: SubmitErrorHandler<AgentFormInput> = (errors) => {
    setErrorCount(countErrors(errors));
  };

  return (
    <FormProvider {...form}>
      <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav aria-label="Form sections" className="hidden lg:block">
          <ol className="sticky top-20 space-y-0.5 text-sm">
            {FORM_SECTIONS.map((section, index) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-fg-muted hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-ring"
                >
                  <span className="w-5 text-right text-xs text-fg-subtle tabular-nums">{index + 1}.</span>
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <form
          noValidate
          aria-label="Agent configuration"
          onSubmit={form.handleSubmit((values) => {
            setErrorCount(0);
            onSubmit(values);
          }, onInvalid)}
          className="min-w-0 space-y-6"
        >
          {errorCount > 0 && Object.keys(form.formState.errors).length > 0 && (
            <Alert tone="danger" role="alert" title={`Please fix ${errorCount} ${errorCount === 1 ? 'problem' : 'problems'} before continuing.`}>
              Invalid fields are marked below. The first one has been focused.
            </Alert>
          )}

          <BasicInfoSection step={1} />
          <DescriptionSection step={2} />
          <CategorySection step={3} />
          <TagsSection step={4} />
          <ModelSection step={5} />
          <ToolsSection step={6} />
          <PermissionsSection step={7} />
          <ResourceLimitsSection step={8} />
          <SecurityPolicySection step={9} />
          <ReviewSection step={10} />

          <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-end gap-2 border-t border-line bg-canvas/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
            <p className="mr-auto text-xs text-fg-subtle">Demo: saved in this browser session only.</p>
            <LinkButton to={cancelTo} variant="secondary">
              Cancel
            </LinkButton>
            <Button type="submit" variant="primary" loading={submitting} disabled={disabled}>
              {submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </FormProvider>
  );
}

function countErrors(value: unknown): number {
  if (!value || typeof value !== 'object') return 0;
  const record = value as Record<string, unknown>;
  if (typeof record.message === 'string' && 'type' in record) return 1;
  return Object.values(record).reduce<number>((sum, child) => sum + countErrors(child), 0);
}
