import { FlaskConical, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useUiStore } from '@/stores/uiStore';
import { Logo } from './Logo';
import { SidebarNav } from './SidebarNav';

/** Desktop sidebar (lg and up). Smaller screens use MobileNav. */
export function Sidebar() {
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-surface transition-[width] lg:flex',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      <div className={cn('flex h-14 items-center border-b border-line', collapsed ? 'justify-center' : 'px-4')}>
        <Logo collapsed={collapsed} />
      </div>
      <div className={cn('flex-1 overflow-y-auto py-4', collapsed ? 'px-2' : 'px-3')}>
        <SidebarNav collapsed={collapsed} />
      </div>
      <div className={cn('space-y-2 border-t border-line py-3', collapsed ? 'px-2' : 'px-3')}>
        {!collapsed && (
          <p className="flex items-start gap-2 rounded-md bg-info-soft px-3 py-2 text-xs text-info">
            <FlaskConical aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            Demo environment. Data is simulated.
          </p>
        )}
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          className={cn(
            'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-fg-muted hover:bg-surface-hover hover:text-fg',
            'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring',
            collapsed && 'justify-center px-0',
          )}
        >
          {collapsed ? <PanelLeftOpen aria-hidden="true" className="size-4" /> : <PanelLeftClose aria-hidden="true" className="size-4" />}
          {!collapsed && 'Collapse'}
        </button>
      </div>
    </aside>
  );
}
