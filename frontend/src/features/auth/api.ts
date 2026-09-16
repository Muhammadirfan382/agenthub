import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Credentials, PasswordChange, ProfileUpdate } from '@/services/contracts';
import { can, type PermissionAction } from '@/services/permissions';
import { queryKeys } from '@/services/queryKeys';
import { useServices } from '@/services/ServicesContext';
import type { SessionInfo } from '@/types/domain';

/**
 * The session is the app's single source of truth about who is signed in.
 * It always comes from the server; nothing about identity is trusted locally.
 */
export function useSession() {
  const { auth } = useServices();
  return useQuery({
    queryKey: queryKeys.auth.session,
    queryFn: () => auth.session(),
    staleTime: 60_000,
    retry: false,
  });
}

export function useCurrentSession(): SessionInfo | null {
  return useSession().data ?? null;
}

/**
 * Role checks for the UI. Hiding a control is a convenience: the backend makes
 * the same check again and refuses the request regardless of what is rendered.
 */
export function usePermission(): (action: PermissionAction, options?: { ownsResource?: boolean }) => boolean {
  const session = useCurrentSession();
  return (action, options) => can(session?.role, action, options);
}

export function useLogin() {
  const { auth } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: Credentials) => auth.login(credentials),
    onSuccess: (session) => {
      // Start from an empty cache: nothing from a previous session survives.
      queryClient.clear();
      queryClient.setQueryData(queryKeys.auth.session, session);
    },
  });
}

export function useLogout() {
  const { auth } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => auth.logout(),
    // Whether or not the call succeeded, this browser is done with the session.
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(queryKeys.auth.session, null);
    },
  });
}

export function useUpdateProfile() {
  const { auth } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: ProfileUpdate) => auth.updateProfile(update),
    onSuccess: (user) =>
      queryClient.setQueryData<SessionInfo | null>(queryKeys.auth.session, (session) =>
        session ? { ...session, user } : session,
      ),
  });
}

export function useChangePassword() {
  const { auth } = useServices();
  return useMutation({ mutationFn: (change: PasswordChange) => auth.changePassword(change) });
}

export function useSwitchOrganization() {
  const { auth } = useServices();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (organizationId: string) => auth.switchOrganization(organizationId),
    onSuccess: (session) => {
      // Another organization means entirely different data.
      queryClient.clear();
      queryClient.setQueryData(queryKeys.auth.session, session);
    },
  });
}
