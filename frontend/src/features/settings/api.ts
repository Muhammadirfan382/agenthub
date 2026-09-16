import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';
import type { Role } from '@/types/domain';

export function useBackendHealthCheck() {
  const { system } = useServices();
  return useMutation({ mutationFn: () => system.checkBackendHealth() });
}

export function useMembers() {
  const { members } = useServices();
  return useQuery({ queryKey: queryKeys.members.list, queryFn: () => members.list() });
}

function useInvalidateMembers() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.members.all });
}

export function useAddMember() {
  const { members } = useServices();
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: Role }) => members.add(email, role),
    onSuccess: invalidate,
  });
}

export function useSetMemberRole() {
  const { members } = useServices();
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) => members.setRole(id, role),
    onSuccess: invalidate,
  });
}

export function useRemoveMember() {
  const { members } = useServices();
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (id: string) => members.remove(id),
    onSuccess: invalidate,
  });
}
