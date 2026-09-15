import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';

export function useDashboardSummary() {
  const { system } = useServices();
  return useQuery({ queryKey: queryKeys.system.summary, queryFn: () => system.dashboardSummary() });
}

export function useComponentStatus() {
  const { system } = useServices();
  return useQuery({ queryKey: queryKeys.system.components, queryFn: () => system.componentStatus() });
}
