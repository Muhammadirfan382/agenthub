import type { LucideIcon } from 'lucide-react';
import type { KeyboardEvent, ReactNode } from 'react';
import { useEffect, useId, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { buttonClasses } from './buttonStyles';

export interface MenuItem {
  id: string;
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  tone?: 'default' | 'danger';
  disabled?: boolean;
}

interface DropdownMenuProps {
  /** Accessible name of the trigger, e.g. "Actions for Research Scout". */
  label: string;
  items: MenuItem[];
  trigger: ReactNode;
  align?: 'start' | 'end';
  triggerClassName?: string;
}

/** Menu button pattern: arrow keys, Home/End, Escape, click outside. */
export function DropdownMenu({ label, items, trigger, align = 'end', triggerClassName }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const enabled = items.map((item, index) => ({ item, index })).filter(({ item }) => !item.disabled);

  useEffect(() => {
    if (!open) return;
    itemRefs.current[enabled[0]?.index ?? 0]?.focus();
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
    // Focus the first item only when the menu opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const close = (restoreFocus = true) => {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  };

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const focusedIndex = itemRefs.current.findIndex((el) => el === document.activeElement);
    const position = enabled.findIndex(({ index }) => index === focusedIndex);
    const move = (to: number) => itemRefs.current[enabled[(to + enabled.length) % enabled.length]?.index ?? 0]?.focus();
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        move(position + 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        move(position - 1);
        break;
      case 'Home':
        event.preventDefault();
        move(0);
        break;
      case 'End':
        event.preventDefault();
        move(enabled.length - 1);
        break;
      case 'Escape':
        event.preventDefault();
        close();
        break;
      case 'Tab':
        close(false);
        break;
    }
  };

  return (
    <div ref={rootRef} className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className={triggerClassName ?? buttonClasses('ghost', 'icon-sm')}
      >
        {trigger}
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={label}
          onKeyDown={onMenuKeyDown}
          className={cn(
            'absolute top-full z-40 mt-1 min-w-44 rounded-lg border border-line bg-surface p-1 shadow-raised animate-fade-in',
            align === 'end' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                ref={(el) => {
                  itemRefs.current[index] = el;
                }}
                type="button"
                role="menuitem"
                tabIndex={-1}
                disabled={item.disabled}
                onClick={() => {
                  close();
                  item.onSelect();
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm',
                  'focus-visible:outline-none focus:bg-surface-hover disabled:opacity-50',
                  item.tone === 'danger' ? 'text-danger hover:bg-danger-soft focus:bg-danger-soft' : 'text-fg hover:bg-surface-hover',
                )}
              >
                {Icon && <Icon aria-hidden="true" className="size-4 shrink-0" />}
                {item.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
