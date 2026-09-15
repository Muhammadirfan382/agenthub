import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { cn } from '@/lib/cn';

export type StatTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info';

const iconTones: Record<StatTone, string> = {
  neutral: 'bg-surface-muted text-fg-muted',
  brand: 'bg-brand-soft text-brand-strong',
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  info: 'bg-info-soft text-info',
};

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon: LucideIcon;
  tone?: StatTone;
  description?: ReactNode;
  to?: string;
}

export function StatCard({ label, value, icon: Icon, tone = 'neutral', description, to }: StatCardProps) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-fg-muted">{label}</p>
        <span className={cn('rounded-md p-1.5', iconTones[tone])}>
          <Icon aria-hidden="true" className="size-4" />
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-fg tabular-nums">{value}</p>
      {description && <p className="mt-1 text-xs text-fg-subtle">{description}</p>}
    </>
  );
  const classes = 'block rounded-lg border border-line bg-surface p-4 shadow-card';
  return to ? (
    <Link to={to} className={cn(classes, 'transition-colors hover:border-line-strong focus-visible:outline-2 focus-visible:outline-ring')}>
      {body}
    </Link>
  ) : (
    <div className={classes}>{body}</div>
  );
}
