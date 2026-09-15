import { X } from 'lucide-react';
import type { MouseEvent, ReactNode, SyntheticEvent } from 'react';
import { useEffect, useId, useRef } from 'react';
import { cn } from '@/lib/cn';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

const sizes = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl' };

/**
 * Modal dialog built on the native <dialog> element: the browser provides the
 * focus trap, inert background, Escape handling and focus restoration.
 */
export function Dialog({ open, onClose, title, description, children, footer, size = 'md' }: DialogProps) {
  if (!open) return null;
  return (
    <DialogSurface onClose={onClose} title={title} description={description} footer={footer} size={size}>
      {children}
    </DialogSurface>
  );
}

function DialogSurface({ onClose, title, description, children, footer, size = 'md' }: Omit<DialogProps, 'open'>) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const onCancel = (event: SyntheticEvent<HTMLDialogElement>) => {
    event.preventDefault();
    onClose();
  };

  const onBackdropClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget) onClose();
  };

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={onCancel}
      onClick={onBackdropClick}
      className={cn(
        'm-auto w-[calc(100%-2rem)] rounded-xl border border-line bg-surface p-0 text-fg shadow-overlay animate-fade-in',
        sizes[size],
      )}
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <h2 id={titleId} className="text-base font-semibold">
            {title}
          </h2>
          {description && (
            <div id={descriptionId} className="mt-1 text-sm text-fg-muted">
              {description}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close dialog"
          className="-mt-1 -mr-1 rounded-md p-1.5 text-fg-subtle hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-ring"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      </div>
      {children && <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>}
      {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
    </dialog>
  );
}
