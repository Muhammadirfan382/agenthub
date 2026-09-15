import { cn } from '@/lib/cn';

export function controlClasses(className?: string): string {
  return cn(
    'w-full rounded-md border border-line bg-surface px-3 text-sm text-fg shadow-card transition-colors',
    'placeholder:text-fg-subtle hover:border-line-strong',
    'focus-visible:border-brand focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-ring',
    'disabled:cursor-not-allowed disabled:opacity-60',
    'aria-invalid:border-danger aria-invalid:focus-visible:outline-danger',
    className,
  );
}
