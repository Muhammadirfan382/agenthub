import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AgentDraft, AgentListParams, PublishInput } from '@/services/contracts';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';
import type { AgentStatus, Visibility } from '@/types/domain';

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
    mutationFn: ({ id, input }: { id: string; input?: string }) =>
      agents.requestExecution(id, input),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.executions.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.system.summary }),
      ]),
  });
}

export function useAgentVersions(id: string) {
  const { agents } = useServices();
  return useQuery({ queryKey: queryKeys.versions.list(id), queryFn: () => agents.versions(id) });
}

/** Publishing changes what the marketplace shows, so both caches are dropped. */
function useInvalidateRegistry(id: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.versions.list(id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.agents.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.marketplace.all }),
    ]);
}

export function usePublishAgent(id: string) {
  const { agents } = useServices();
  const invalidate = useInvalidateRegistry(id);
  return useMutation({
    mutationFn: (input: PublishInput) => agents.publish(id, input),
    onSuccess: invalidate,
  });
}

export function useSetAgentVisibility(id: string) {
  const { agents } = useServices();
  const invalidate = useInvalidateRegistry(id);
  return useMutation({
    mutationFn: (visibility: Visibility) => agents.setVisibility(id, visibility),
    onSuccess: invalidate,
  });
}
