import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from 'lucide-react';
import { useEffect } from 'react';
import { cn } from '@/lib/cn';
import { type Toast, type ToastTone, useToastStore } from '@/stores/toastStore';

const AUTO_DISMISS_MS = 5000;

const tones: Record<ToastTone, { Icon: typeof Info; classes: string }> = {
  success: { Icon: CircleCheck, classes: 'text-success' },
  info: { Icon: Info, classes: 'text-info' },
  warning: { Icon: TriangleAlert, classes: 'text-warning' },
  danger: { Icon: CircleAlert, classes: 'text-danger' },
};

/** Success and failure feedback. Announced politely to screen readers. */
export function Toaster() {
  const toasts = useToastStore((state) => state.toasts);
  return (
    <div
      aria-live="polite"
      aria-label="Notifications"
      role="region"
      className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((state) => state.dismiss);
  const { Icon, classes } = tones[toast.tone];

  useEffect(() => {
    const timer = window.setTimeout(() => dismiss(toast.id), AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [dismiss, toast.id]);

  return (
    <div className="pointer-events-auto flex items-start gap-3 rounded-lg border border-line bg-surface p-3 shadow-overlay animate-fade-in">
      <Icon aria-hidden="true" className={cn('mt-0.5 size-4 shrink-0', classes)} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">{toast.title}</p>
        {toast.description && <p className="mt-0.5 text-xs text-fg-muted">{toast.description}</p>}
      </div>
      <button
        type="button"
        onClick={() => dismiss(toast.id)}
        aria-label="Dismiss notification"
        className="rounded p-1 text-fg-subtle hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-ring"
      >
        <X aria-hidden="true" className="size-3.5" />
      </button>
    </div>
  );
}
