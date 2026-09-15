import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';

export function useAnalyticsSummary() {
  const { analytics } = useServices();
  return useQuery({ queryKey: queryKeys.analytics.summary, queryFn: () => analytics.summary() });
}
