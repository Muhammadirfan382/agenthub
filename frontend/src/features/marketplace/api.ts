import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { MarketplaceParams } from '@/services/contracts';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';

export function useMarketplace(params: MarketplaceParams = {}) {
  const { marketplace } = useServices();
  return useQuery({
    queryKey: queryKeys.marketplace.list(params),
    queryFn: () => marketplace.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useMarketplaceTags() {
  const { marketplace } = useServices();
  return useQuery({ queryKey: queryKeys.marketplace.tags, queryFn: () => marketplace.tags() });
}
