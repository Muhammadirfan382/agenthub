import { useId } from 'react';
import { cn } from '@/lib/cn';

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
  className?: string;
}

export function Switch({ checked, onCheckedChange, label, description, disabled, className }: SwitchProps) {
  const id = useId();
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        <span id={`${id}-label`} className="text-sm font-medium text-fg">
          {label}
        </span>
        {description && (
          <p id={`${id}-description`} className="mt-0.5 text-xs text-fg-muted">
            {description}
          </p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={description ? `${id}-description` : undefined}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50',
          checked ? 'border-brand bg-brand' : 'border-line-strong bg-surface-muted',
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            'inline-block size-3.5 rounded-full shadow-card transition-transform',
            checked ? 'translate-x-4 bg-brand-fg' : 'translate-x-0.5 bg-fg-subtle',
          )}
        />
      </button>
    </div>
  );
}
