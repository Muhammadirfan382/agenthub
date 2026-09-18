import { Link } from 'react-router';
import { Alert } from '@/components/ui/Alert';
import { formatDateTime } from '@/lib/format';
import { usePendingApprovals, useRuntimeState } from '../api';

/**
 * Two things people need to know without going looking: everything is stopped,
 * or something is waiting for them.
 */
export function RuntimeBanner({ className }: { className?: string }) {
  const runtime = useRuntimeState();
  const approvals = usePendingApprovals();
  const paused = runtime.data?.executionsPaused ?? false;
  const waiting = approvals.data ?? [];

  if (!paused && waiting.length === 0) return null;

  return (
    <div className={className}>
      {paused && (
        <Alert tone="danger" title="Executions are stopped for this organization" className="mb-3">
          {runtime.data?.pausedBy ? `Engaged by ${runtime.data.pausedBy}` : 'Engaged'}
          {runtime.data?.pausedAt ? ` on ${formatDateTime(runtime.data.pausedAt)}` : ''}
          {runtime.data?.reason ? `: ${runtime.data.reason}` : '.'} Nothing new starts until the
          owner releases the kill switch in Settings → Runtime.
        </Alert>
      )}

      {waiting.length > 0 && (
        <Alert
          tone="warning"
          title={`${waiting.length} ${waiting.length === 1 ? 'step is' : 'steps are'} waiting for approval`}
        >
          <ul className="space-y-1">
            {waiting.slice(0, 3).map((approval) => (
              <li key={approval.id}>
                <Link
                  to={`/executions/${approval.executionId}`}
                  className="font-medium text-brand-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {approval.agentName}
                </Link>{' '}
                — {approval.tool ?? approval.capability}
              </li>
            ))}
            {waiting.length > 3 && <li>and {waiting.length - 3} more.</li>}
          </ul>
        </Alert>
      )}
    </div>
  );
}
