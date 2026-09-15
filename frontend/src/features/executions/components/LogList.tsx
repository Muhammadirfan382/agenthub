import { cn } from '@/lib/cn';
import { formatTime } from '@/lib/format';
import type { LogEntry, LogLevel } from '@/types/domain';

const LEVEL: Record<LogLevel, string> = {
  debug: 'text-fg-subtle',
  info: 'text-info',
  warn: 'text-warning',
  error: 'text-danger',
};

/** Static log listing. Not a live region: these logs are not streamed. */
export function LogList({ logs }: { logs: LogEntry[] }) {
  if (logs.length === 0) return <p className="text-sm text-fg-muted">No log entries.</p>;
  return (
    <ol aria-label="Execution logs" className="max-h-96 overflow-auto rounded-md border border-line bg-surface-muted p-3 font-mono text-xs leading-relaxed">
      {logs.map((log) => (
        <li key={log.id} className="flex flex-wrap gap-x-3">
          <span className="text-fg-subtle">{formatTime(log.at)}</span>
          <span className={cn('w-12 font-semibold uppercase', LEVEL[log.level])}>{log.level}</span>
          <span className="min-w-0 flex-1 break-words text-fg">{log.message}</span>
        </li>
      ))}
    </ol>
  );
}
