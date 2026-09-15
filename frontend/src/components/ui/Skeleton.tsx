import { cn } from '@/lib/cn';

/** Decorative placeholder. Loading announcements come from LoadingState. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('animate-pulse rounded-md bg-surface-muted', className)} />;
}
