import { cn } from '@/lib/cn';

export type MeterTone = 'brand' | 'success' | 'warning' | 'high' | 'danger' | 'info';

const fills: Record<MeterTone, string> = {
  brand: 'bg-brand',
  success: 'bg-success',
  warning: 'bg-warning',
  high: 'bg-high',
  danger: 'bg-danger',
  info: 'bg-info',
};

interface MeterProps {
  value: number;
  max?: number;
  label: string;
  /** Spoken value, e.g. "72 out of 100, high risk". */
  valueText?: string;
  tone?: MeterTone;
  className?: string;
}

export function Meter({ value, max = 100, label, valueText, tone = 'brand', className }: MeterProps) {
  const clamped = Math.max(0, Math.min(max, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={clamped}
      aria-valuetext={valueText}
      className={cn('h-2 w-full overflow-hidden rounded-full bg-surface-muted', className)}
    >
      <div className={cn('h-full rounded-full', fills[tone])} style={{ width: `${(clamped / max) * 100}%` }} />
    </div>
  );
}
