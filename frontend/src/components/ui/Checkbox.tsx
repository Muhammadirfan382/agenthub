import type { ComponentProps, ReactNode } from 'react';
import { useId } from 'react';
import { cn } from '@/lib/cn';

interface CheckboxProps extends Omit<ComponentProps<'input'>, 'type'> {
  label: ReactNode;
  description?: ReactNode;
}

export function Checkbox({ label, description, className, id, ...props }: CheckboxProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const descriptionId = description ? `${inputId}-description` : undefined;

  return (
    <div className={cn('flex items-start gap-3', className)}>
      <input
        id={inputId}
        type="checkbox"
        aria-describedby={descriptionId}
        className="mt-0.5 size-4 shrink-0 rounded border-line-strong accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        {...props}
      />
      <div className="min-w-0">
        <label htmlFor={inputId} className="text-sm font-medium text-fg">
          {label}
        </label>
        {description && (
          <p id={descriptionId} className="mt-0.5 text-xs text-fg-muted">
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
