import { Building2, ChevronDown, LogOut, User, Users } from 'lucide-react';
import { useNavigate } from 'react-router';
import { DropdownMenu } from '@/components/ui/DropdownMenu';
import { useCurrentSession, useLogout } from '@/features/auth/api';
import { useServices } from '@/services/ServicesContext';
import { ROLE_LABELS } from '@/types/domain';

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

export function UserMenu() {
  const navigate = useNavigate();
  const session = useCurrentSession();
  const logout = useLogout();
  const { dataSource } = useServices();

  const name = session?.user.name ?? 'Signed out';
  const subtitle = session ? `${session.organization.name} · ${ROLE_LABELS[session.role]}` : 'No session';

  return (
    <DropdownMenu
      label={`Account menu for ${name}`}
      triggerClassName="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-ring"
      trigger={
        <>
          <span aria-hidden="true" className="grid size-7 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand-strong">
            {initials(name)}
          </span>
          <span className="hidden text-left md:block">
            <span className="block text-xs leading-tight font-medium text-fg">{name}</span>
            <span className="block text-[11px] leading-tight text-fg-subtle">{subtitle}</span>
          </span>
          <ChevronDown aria-hidden="true" className="hidden size-3.5 text-fg-subtle md:block" />
        </>
      }
      items={[
        {
          id: 'profile',
          label: 'Profile settings',
          icon: User,
          onSelect: () => navigate('/settings?section=profile'),
        },
        {
          id: 'organization',
          label: dataSource === 'demo' ? 'Demo workspace' : (session?.organization.name ?? 'Organization'),
          icon: Building2,
          disabled: true,
          onSelect: () => undefined,
        },
        {
          id: 'members',
          label: 'Members',
          icon: Users,
          onSelect: () => navigate('/settings?section=members'),
        },
        {
          id: 'signout',
          label: logout.isPending ? 'Signing out…' : 'Sign out',
          icon: LogOut,
          disabled: logout.isPending,
          onSelect: () =>
            logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) }),
        },
      ]}
    />
  );
}
