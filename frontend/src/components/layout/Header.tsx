import { Menu, Plus } from 'lucide-react';
import { LinkButton } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonStyles';
import { DemoBadge } from '@/components/feedback/DemoNotice';
import { useUiStore } from '@/stores/uiStore';
import { LogoMark } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { UserMenu } from './UserMenu';

export function Header() {
  const mobileNavOpen = useUiStore((state) => state.mobileNavOpen);
  const setMobileNavOpen = useUiStore((state) => state.setMobileNavOpen);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-surface/75 sm:px-6">
      <button
        type="button"
        onClick={() => setMobileNavOpen(true)}
        aria-label="Open navigation"
        aria-expanded={mobileNavOpen}
        className={buttonClasses('ghost', 'icon', 'lg:hidden')}
      >
        <Menu aria-hidden="true" className="size-5" />
      </button>
      <span className="lg:hidden">
        <LogoMark className="size-6" />
      </span>

      <div className="hidden sm:block">
        <DemoBadge label="Demo mode" />
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        <LinkButton to="/agents/create" variant="primary" size="sm" className="hidden sm:inline-flex">
          <Plus aria-hidden="true" className="size-4" />
          Create agent
        </LinkButton>
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
