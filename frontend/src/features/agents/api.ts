import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AgentDraft, AgentListParams } from '@/services/contracts';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';
import type { AgentStatus } from '@/types/domain';

export function useAgents(params: AgentListParams = {}) {
  const { agents } = useServices();
  return useQuery({
    queryKey: queryKeys.agents.list(params),
    queryFn: () => agents.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useAgent(id: string) {
  const { agents } = useServices();
  return useQuery({ queryKey: queryKeys.agents.detail(id), queryFn: () => agents.get(id) });
}

/** Agent changes affect dashboard counts and the security overview too. */
function useInvalidateAgentData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.agents.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.system.summary }),
      queryClient.invalidateQueries({ queryKey: queryKeys.security.overview }),
    ]);
}

export function useCreateAgent() {
  const { agents } = useServices();
  const invalidate = useInvalidateAgentData();
  return useMutation({ mutationFn: (draft: AgentDraft) => agents.create(draft), onSuccess: invalidate });
}

export function useUpdateAgent(id: string) {
  const { agents } = useServices();
  const invalidate = useInvalidateAgentData();
  return useMutation({ mutationFn: (draft: AgentDraft) => agents.update(id, draft), onSuccess: invalidate });
}

export function useDeleteAgent() {
  const { agents } = useServices();
  const invalidate = useInvalidateAgentData();
  return useMutation({ mutationFn: (id: string) => agents.remove(id), onSuccess: invalidate });
}

export function useSetAgentStatus() {
  const { agents } = useServices();
  const invalidate = useInvalidateAgentData();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: AgentStatus }) => agents.setStatus(id, status),
    onSuccess: invalidate,
  });
}

export function useRequestExecution() {
  const { agents } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => agents.requestExecution(id),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.executions.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.system.summary }),
      ]),
  });
}
