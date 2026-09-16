import type { Execution } from '@/types/domain';

/** Short, human-readable outcome for tables and lists. */
export function executionResultText(execution: Execution): string {
  switch (execution.status) {
    case 'COMPLETED':
      return execution.resultSummary ?? 'Completed';
    case 'FAILED':
      // The cause is only known once the runtime records one.
      return execution.resultSummary ?? 'Failed';
    case 'TIMEOUT':
      return 'Stopped at runtime limit';
    case 'CANCELLED':
      return 'Cancelled by user';
    case 'QUEUED':
      return 'Waiting to start';
    case 'STARTING':
    case 'RUNNING':
    case 'WAITING_FOR_TOOL':
      return 'In progress';
  }
}

export function totalTokens(execution: Execution): number {
  return execution.tokenUsage.input + execution.tokenUsage.output;
}
