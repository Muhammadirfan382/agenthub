import { useQuery } from '@tanstack/react-query';
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

export function usePolicies() {
  const { security } = useServices();
  return useQuery({ queryKey: queryKeys.security.policies, queryFn: () => security.policies() });
}
