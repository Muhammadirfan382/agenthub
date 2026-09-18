import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { appConfig } from '@/config/env';
import type { ExecutionListParams } from '@/services/contracts';
import { executionStreamUrl } from '@/services/http/executionApi';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';
import type { ApprovalDecision, ExecutionStatus } from '@/types/domain';
import { isExecutionFinished } from '@/types/domain';

/** How often an unfinished run is re-read when the event stream is unavailable. */
const LIVE_POLL_MS = 3000;

function anyRunning(statuses: ExecutionStatus[]): boolean {
  return statuses.some((status) => !isExecutionFinished(status));
}

export function useExecutions(params: ExecutionListParams = {}) {
  const { executions, dataSource } = useServices();
  return useQuery({
    queryKey: queryKeys.executions.list(params),
    queryFn: () => executions.list(params),
    placeholderData: keepPreviousData,
    // A list containing live runs refreshes itself; a finished one does not.
    // Demo data never changes behind the app's back, so it never polls.
    refetchInterval: (query) =>
      dataSource === 'api' &&
      anyRunning((query.state.data ?? []).map((execution) => execution.status))
        ? LIVE_POLL_MS
        : false,
  });
}

export function useExecution(id: string) {
  const { executions, dataSource } = useServices();
  return useQuery({
    queryKey: queryKeys.executions.detail(id),
    queryFn: () => executions.get(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const live = Boolean(status && !isExecutionFinished(status));
      return dataSource === 'api' && live ? LIVE_POLL_MS : false;
    },
  });
}

/**
 * Subscribes to the server's event stream for one execution.
 *
 * The stream is an optimisation, not a dependency: every view also polls while
 * a run is live, so a browser without `EventSource` — or a proxy that buffers
 * the stream — still sees the run progress, just a little later.
 */
export function useExecutionStream(id: string, enabled: boolean): void {
  const { dataSource } = useServices();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || dataSource !== 'api' || typeof EventSource === 'undefined') return;

    const source = new EventSource(executionStreamUrl(id, appConfig.apiBaseUrl), {
      withCredentials: true,
    });
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.executions.detail(id) });
    };
    source.addEventListener('timeline', refresh);
    source.addEventListener('status', refresh);
    source.addEventListener('finished', () => {
      refresh();
      source.close();
    });
    // A dropped stream is not worth showing as an error: polling covers it.
    source.onerror = () => source.close();

    return () => source.close();
  }, [id, enabled, dataSource, queryClient]);
}

function useInvalidateExecutions() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.executions.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.runtime.all }),
    ]);
}

export function useCancelExecution() {
  const { executions } = useServices();
  const invalidate = useInvalidateExecutions();
  return useMutation({
    mutationFn: (id: string) => executions.cancel(id),
    onSuccess: invalidate,
  });
}

export function usePendingApprovals() {
  const { executions, dataSource } = useServices();
  return useQuery({
    queryKey: queryKeys.executions.approvals,
    queryFn: () => executions.pendingApprovals(),
    refetchInterval: dataSource === 'api' ? LIVE_POLL_MS : false,
  });
}

export interface ApprovalInput {
  executionId: string;
  approvalId: string;
  decision: ApprovalDecision;
  note?: string;
}

export function useDecideApproval() {
  const { executions } = useServices();
  const invalidate = useInvalidateExecutions();
  return useMutation({
    mutationFn: ({ executionId, approvalId, decision, note }: ApprovalInput) =>
      executions.decideApproval(executionId, approvalId, decision, note),
    onSuccess: invalidate,
  });
}

export function useRuntimeState() {
  const { runtime } = useServices();
  return useQuery({ queryKey: queryKeys.runtime.state, queryFn: () => runtime.state() });
}

/** Which tiers a real model answers, the limits, and today's usage. */
export function useModelGatewayStatus() {
  const { runtime } = useServices();
  return useQuery({ queryKey: queryKeys.runtime.models, queryFn: () => runtime.models() });
}

/** Reads the sandbox configuration. Asking starts no container. */
export function useSandboxStatus() {
  const { runtime } = useServices();
  return useQuery({ queryKey: queryKeys.runtime.sandbox, queryFn: () => runtime.sandbox() });
}

/** Starts one throwaway container and reports what it could do. */
export function useCheckSandbox() {
  const { runtime } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => runtime.checkSandbox(),
    // A check that reached a runtime is fresher news than the cached status.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.runtime.sandbox }),
  });
}

export function useSetExecutionsPaused() {
  const { runtime } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ paused, reason }: { paused: boolean; reason?: string }) =>
      runtime.setExecutionsPaused(paused, reason),
    onSuccess: (state) => {
      queryClient.setQueryData(queryKeys.runtime.state, state);
      return queryClient.invalidateQueries({ queryKey: queryKeys.executions.all });
    },
  });
}
