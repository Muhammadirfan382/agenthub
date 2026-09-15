import { Plus, X } from 'lucide-react';
import { type KeyboardEvent, useId, useState } from 'react';
import { useFormContext, useWatch } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { FormSection } from '../FormSection';
import type { AgentFormInput } from '../schema';

export function TagsSection({ step }: { step: number }) {
  const { control, setValue, formState } = useFormContext<AgentFormInput>();
  const tags = useWatch({ control, name: 'tags' });
  const [draft, setDraft] = useState('');
  const id = useId();
  const error = formState.errors.tags?.message ?? formState.errors.tags?.root?.message ?? tagItemError(formState.errors.tags);

  const add = () => {
    const value = draft.trim().toLowerCase();
    if (!value) return;
    setValue('tags', [...tags, value], { shouldValidate: true, shouldDirty: true, shouldTouch: true });
    setDraft('');
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      add();
    }
  };

  return (
    <FormSection id="tags" step={step} title="Tags" description="Lowercase keywords, up to 10.">
      <div className="space-y-1.5">
        <label htmlFor={`${id}-input`} className="text-sm font-medium text-fg">
          Add tag <span className="text-danger" aria-hidden="true">*</span>
        </label>
        <div className="flex gap-2 sm:max-w-md">
          <Input
            id={`${id}-input`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="e.g. research"
            aria-describedby={`${id}-hint${error ? ` ${id}-error` : ''}`}
            aria-invalid={error ? true : undefined}
            autoComplete="off"
          />
          <Button variant="secondary" onClick={add} disabled={!draft.trim()}>
            <Plus aria-hidden="true" className="size-4" />
            Add
          </Button>
        </div>
        <p id={`${id}-hint`} className="text-xs text-fg-muted">
          Press Enter or comma to add. {tags.length}/10 tags.
        </p>
        {error && (
          <p id={`${id}-error`} className="text-xs font-medium text-danger">
            {error}
          </p>
        )}
      </div>
      {tags.length > 0 && (
        <ul aria-label="Selected tags" className="flex flex-wrap gap-2">
          {tags.map((tag, index) => (
            <li key={`${tag}-${index}`} className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-muted py-0.5 pr-1 pl-2.5 text-xs text-fg">
              {tag}
              <button
                type="button"
                aria-label={`Remove tag ${tag}`}
                onClick={() => setValue('tags', tags.filter((_, i) => i !== index), { shouldValidate: true, shouldDirty: true })}
                className="rounded-full p-0.5 text-fg-subtle hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-ring"
              >
                <X aria-hidden="true" className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </FormSection>
  );
}

function tagItemError(errors: unknown): string | undefined {
  if (!Array.isArray(errors)) return undefined;
  const first = errors.find((e): e is { message?: string } => Boolean(e && typeof e === 'object' && 'message' in e));
  return first?.message;
}
