import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { InstallationPatch, InstallInput, MarketplaceParams } from '@/services/contracts';
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

export function useListing(id: string) {
  const { marketplace } = useServices();
  return useQuery({
    queryKey: queryKeys.marketplace.detail(id),
    queryFn: () => marketplace.get(id),
  });
}

export function useMarketplaceTags() {
  const { marketplace } = useServices();
  return useQuery({ queryKey: queryKeys.marketplace.tags, queryFn: () => marketplace.tags() });
}

export function useInstallations() {
  const { installations } = useServices();
  return useQuery({ queryKey: queryKeys.installations.list, queryFn: () => installations.list() });
}

export function useInstallation(id: string) {
  const { installations } = useServices();
  return useQuery({
    queryKey: queryKeys.installations.detail(id),
    queryFn: () => installations.get(id),
  });
}

/** Installing changes the listing too: it is now marked as installed. */
function useInvalidateInstallations() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.installations.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.marketplace.all }),
    ]);
}

export function useInstall() {
  const { installations } = useServices();
  const invalidate = useInvalidateInstallations();
  return useMutation({
    mutationFn: (input: InstallInput) => installations.install(input),
    onSuccess: invalidate,
  });
}

export function useUpdateInstallation(id: string) {
  const { installations } = useServices();
  const invalidate = useInvalidateInstallations();
  return useMutation({
    mutationFn: (patch: InstallationPatch) => installations.update(id, patch),
    onSuccess: invalidate,
  });
}

export function useUninstall() {
  const { installations } = useServices();
  const invalidate = useInvalidateInstallations();
  return useMutation({
    mutationFn: (id: string) => installations.uninstall(id),
    onSuccess: invalidate,
  });
}
