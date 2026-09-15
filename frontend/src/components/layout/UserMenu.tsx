import { ChevronDown, LogOut, User } from 'lucide-react';
import { useNavigate } from 'react-router';
import { DropdownMenu } from '@/components/ui/DropdownMenu';
import { useCurrentUser } from '@/features/settings/api';

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

/** Shows the placeholder demo profile. There is no authentication yet. */
export function UserMenu() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const name = user?.name ?? 'Demo User';

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
            <span className="block text-[11px] leading-tight text-fg-subtle">Demo session</span>
          </span>
          <ChevronDown aria-hidden="true" className="hidden size-3.5 text-fg-subtle md:block" />
        </>
      }
      items={[
        { id: 'profile', label: 'Profile settings', icon: User, onSelect: () => navigate('/settings?section=profile') },
        { id: 'signout', label: 'Sign out (not available yet)', icon: LogOut, disabled: true, onSelect: () => undefined },
      ]}
    />
  );
}
