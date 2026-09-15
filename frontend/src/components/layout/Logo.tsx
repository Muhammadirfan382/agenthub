import { Link } from 'react-router';
import { cn } from '@/lib/cn';

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn('size-7', className)}>
      <rect width="32" height="32" rx="8" className="fill-brand" />
      <path d="M16 6.5 24.5 11v10L16 25.5 7.5 21V11z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" className="text-brand-fg" />
      <circle cx="16" cy="16" r="3" className="fill-brand-fg" />
    </svg>
  );
}

export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Link to="/dashboard" className="flex items-center gap-2.5 rounded-md focus-visible:outline-2 focus-visible:outline-ring" aria-label="AgentHub home">
      <LogoMark />
      {!collapsed && <span className="text-base font-semibold tracking-tight text-fg">AgentHub</span>}
    </Link>
  );
}
