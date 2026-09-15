import { NavLink } from 'react-router';
import { cn } from '@/lib/cn';
import { NAV_SECTIONS } from './navigation';

interface SidebarNavProps {
  collapsed?: boolean;
  onNavigate?: () => void;
}

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-5">
      {NAV_SECTIONS.map((section) => (
        <div key={section.title}>
          <p className={cn('px-3 pb-1.5 text-[11px] font-semibold tracking-wider text-fg-subtle uppercase', collapsed && 'sr-only')}>
            {section.title}
          </p>
          <ul className="space-y-0.5">
            {section.items.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  onClick={onNavigate}
                  title={collapsed ? label : undefined}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring',
                      collapsed && 'justify-center px-0',
                      isActive ? 'bg-brand-soft text-brand-strong' : 'text-fg-muted hover:bg-surface-hover hover:text-fg',
                    )
                  }
                >
                  <Icon aria-hidden="true" className="size-4 shrink-0" />
                  <span className={cn(collapsed && 'sr-only')}>{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
