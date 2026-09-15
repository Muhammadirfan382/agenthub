import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export type AlertTone = 'info' | 'success' | 'warning' | 'danger';

const tones: Record<AlertTone, { classes: string; Icon: typeof Info }> = {
  info: { classes: 'border-info/25 bg-info-soft text-info', Icon: Info },
  success: { classes: 'border-success/25 bg-success-soft text-success', Icon: CircleCheck },
  warning: { classes: 'border-warning/25 bg-warning-soft text-warning', Icon: TriangleAlert },
  danger: { classes: 'border-danger/25 bg-danger-soft text-danger', Icon: CircleAlert },
};

interface AlertProps {
  tone?: AlertTone;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  /** Use "alert" only for urgent, dynamically inserted messages. */
  role?: 'status' | 'alert';
  className?: string;
}

export function Alert({ tone = 'info', title, children, action, role, className }: AlertProps) {
  const { classes, Icon } = tones[tone];
  return (
    <div role={role} className={cn('flex gap-3 rounded-lg border px-4 py-3', classes, className)}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{title}</p>
        {children && <div className="mt-0.5 text-sm text-fg-muted">{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  );
}
