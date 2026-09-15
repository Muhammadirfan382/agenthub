import type { KeyboardEvent, ReactNode } from 'react';
import { useRef } from 'react';
import { cn } from '@/lib/cn';

export interface TabItem<T extends string> {
  id: T;
  label: string;
  count?: number;
}

interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  /** Shared with TabPanel so tabs and panels reference each other. */
  idPrefix: string;
  className?: string;
}

/** ARIA tabs with roving tabindex and arrow-key navigation. */
export function Tabs<T extends string>({ items, value, onChange, label, idPrefix, className }: TabsProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = items.findIndex((item) => item.id === value);
    let next: number;
    if (event.key === 'ArrowRight') next = (current + 1) % items.length;
    else if (event.key === 'ArrowLeft') next = (current - 1 + items.length) % items.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    else return;
    event.preventDefault();
    const target = items[next];
    if (target) {
      onChange(target.id);
      refs.current[next]?.focus();
    }
  };

  return (
    <div className={cn('overflow-x-auto border-b border-line', className)}>
      <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex min-w-max gap-1">
        {items.map((item, index) => {
          const selected = item.id === value;
          return (
            <button
              key={item.id}
              ref={(el) => {
                refs.current[index] = el;
              }}
              type="button"
              role="tab"
              id={`${idPrefix}-tab-${item.id}`}
              aria-selected={selected}
              aria-controls={`${idPrefix}-panel-${item.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(item.id)}
              className={cn(
                '-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
                'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring',
                selected ? 'border-brand text-fg' : 'border-transparent text-fg-muted hover:text-fg',
              )}
            >
              {item.label}
              {item.count !== undefined && (
                <span className="rounded-full bg-surface-muted px-1.5 text-xs text-fg-muted tabular-nums">{item.count}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface TabPanelProps {
  idPrefix: string;
  id: string;
  children: ReactNode;
  className?: string;
}

export function TabPanel({ idPrefix, id, children, className }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${id}`}
      aria-labelledby={`${idPrefix}-tab-${id}`}
      tabIndex={0}
      className={cn('focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring', className)}
    >
      {children}
    </div>
  );
}
