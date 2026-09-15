import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { ExecutionListParams } from '@/services/contracts';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';

export function useExecutions(params: ExecutionListParams = {}) {
  const { executions } = useServices();
  return useQuery({
    queryKey: queryKeys.executions.list(params),
    queryFn: () => executions.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useExecution(id: string) {
  const { executions } = useServices();
  return useQuery({ queryKey: queryKeys.executions.detail(id), queryFn: () => executions.get(id) });
}
