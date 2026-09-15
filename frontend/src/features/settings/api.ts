import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ProfileUpdate } from '@/services/contracts';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';

export function useCurrentUser() {
  const { auth } = useServices();
  return useQuery({ queryKey: queryKeys.auth.currentUser, queryFn: () => auth.currentUser() });
}

export function useUpdateProfile() {
  const { auth } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: ProfileUpdate) => auth.updateProfile(update),
    onSuccess: (user) => queryClient.setQueryData(queryKeys.auth.currentUser, user),
  });
}

export function useBackendHealthCheck() {
  const { system } = useServices();
  return useMutation({ mutationFn: () => system.checkBackendHealth() });
}
