import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';

export function useSecurityOverview() {
  const { security } = useServices();
  return useQuery({ queryKey: queryKeys.security.overview, queryFn: () => security.overview() });
}

export function useSecurityEvents() {
  const { security } = useServices();
  return useQuery({ queryKey: queryKeys.security.events, queryFn: () => security.events() });
}

export function useAlerts(state?: 'firing' | 'resolved') {
  const { alerts, dataSource } = useServices();
  return useQuery({
    queryKey: queryKeys.alerts.list(state),
    queryFn: () => alerts.list(state),
    // Alerts change behind the app's back only when there is a backend.
    refetchInterval: dataSource === 'api' ? 30_000 : false,
  });
}

export function useResolveAlert() {
  const { alerts } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alerts.resolve(id),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.system.summary }),
        queryClient.invalidateQueries({ queryKey: queryKeys.system.components }),
      ]),
  });
}

export function usePolicies() {
  const { security } = useServices();
  return useQuery({ queryKey: queryKeys.security.policies, queryFn: () => security.policies() });
}
