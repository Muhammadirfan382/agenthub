import type { LucideIcon } from 'lucide-react';
import { CircleCheck, CircleDot, CircleX, Cpu, Scale, Wrench } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatTime } from '@/lib/format';
import type { TimelineEvent, TimelineEventKind } from '@/types/domain';

const KIND: Record<TimelineEventKind, { icon: LucideIcon; label: string; classes: string }> = {
  lifecycle: { icon: CircleDot, label: 'Lifecycle', classes: 'border-line-strong bg-surface-muted text-fg-muted' },
  model: { icon: Cpu, label: 'Model', classes: 'border-brand/30 bg-brand-soft text-brand-strong' },
  tool: { icon: Wrench, label: 'Tool', classes: 'border-info/30 bg-info-soft text-info' },
  policy: { icon: Scale, label: 'Policy', classes: 'border-warning/30 bg-warning-soft text-warning' },
  error: { icon: CircleX, label: 'Error', classes: 'border-danger/30 bg-danger-soft text-danger' },
  result: { icon: CircleCheck, label: 'Result', classes: 'border-success/30 bg-success-soft text-success' },
};

export function ExecutionTimeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-fg-muted">No events recorded.</p>;
  return (
    <ol aria-label="Execution timeline" className="space-y-0">
      {events.map((event, index) => {
        const meta = KIND[event.kind];
        const Icon = meta.icon;
        const last = index === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
            {!last && <span aria-hidden="true" className="absolute top-8 left-[13px] h-[calc(100%-1.5rem)] w-px bg-line" />}
            <span className={cn('relative grid size-7 shrink-0 place-items-center rounded-full border', meta.classes)}>
              <Icon aria-hidden="true" className="size-3.5" />
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="text-sm font-medium text-fg">
                <span className="sr-only">{meta.label}: </span>
                {event.label}
              </p>
              <p className="font-mono text-xs text-fg-subtle">{formatTime(event.at)}</p>
              {event.detail && <p className="mt-1 text-sm text-fg-muted">{event.detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
