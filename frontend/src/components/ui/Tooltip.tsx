import type { ReactNode } from 'react';
import { useEffect, useId, useState } from 'react';
import { cn } from '@/lib/cn';

interface TooltipProps {
  content: string;
  /** Receives the attribute the trigger must spread. Tooltips supplement, never replace, visible text. */
  children: (trigger: { 'aria-describedby': string }) => ReactNode;
  className?: string;
}

/** Shows on hover and keyboard focus; dismissible with Escape (WCAG 1.4.13). */
export function Tooltip({ content, children, className }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children({ 'aria-describedby': id })}
      <span
        role="tooltip"
        id={id}
        className={cn(
          'pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-64 -translate-x-1/2 rounded-md bg-fg px-2 py-1 text-xs text-canvas shadow-raised',
          open ? 'visible opacity-100' : 'invisible opacity-0',
        )}
      >
        {content}
      </span>
    </span>
  );
}
