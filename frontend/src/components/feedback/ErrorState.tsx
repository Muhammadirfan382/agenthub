import { RotateCw, TriangleAlert } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}

/** Shown when data fails to load. Never renders raw error details or stack traces. */
export function ErrorState({
  title = 'Something went wrong',
  message = 'The data could not be loaded. Please try again.',
  onRetry,
  retrying = false,
  className,
}: ErrorStateProps) {
  return (
    <div role="alert" className={cn('flex flex-col items-center justify-center rounded-lg border border-danger/25 bg-danger-soft px-6 py-10 text-center', className)}>
      <span className="mb-3 rounded-lg border border-danger/25 bg-surface p-2.5 text-danger">
        <TriangleAlert aria-hidden="true" className="size-5" />
      </span>
      <h2 className="text-base font-semibold text-fg">{title}</h2>
      <p className="mt-1 max-w-md text-sm text-fg-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry} loading={retrying}>
          {!retrying && <RotateCw aria-hidden="true" className="size-4" />}
          Try again
        </Button>
      )}
    </div>
  );
}
