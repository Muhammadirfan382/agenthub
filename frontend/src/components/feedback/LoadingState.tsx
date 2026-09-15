import { Skeleton } from '@/components/ui/Skeleton';
import { Spinner } from '@/components/ui/Spinner';
import { cn } from '@/lib/cn';

interface LoadingStateProps {
  label?: string;
  variant?: 'page' | 'table' | 'cards' | 'inline';
  className?: string;
}

/** Announces loading to assistive technology and shows a matching skeleton. */
export function LoadingState({ label = 'Loading…', variant = 'page', className }: LoadingStateProps) {
  return (
    <div role="status" aria-live="polite" className={cn('w-full', className)}>
      {variant === 'inline' ? (
        <span className="inline-flex items-center gap-2 text-sm text-fg-muted">
          <Spinner />
          {label}
        </span>
      ) : (
        <>
          <span className="sr-only">{label}</span>
          {variant === 'table' && <TableSkeleton />}
          {variant === 'cards' && <CardsSkeleton />}
          {variant === 'page' && <PageSkeleton />}
        </>
      )}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2 rounded-lg border border-line bg-surface p-4">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

function CardsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="space-y-3 rounded-lg border border-line bg-surface p-4">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-6 w-1/3" />
        </div>
      ))}
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-7 w-64" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-64 w-full rounded-lg" />
    </div>
  );
}
