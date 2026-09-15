import { UserCog } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/cn';
import type { AgentPermission } from '@/types/domain';
import { CAPABILITY_META, PERMISSION_LEVEL_META } from './meta';
import { RiskBadge } from './StatusBadges';

/** One capability with its grant level, scope, risk and approval requirement. */
export function PermissionIndicator({ permission, className }: { permission: AgentPermission; className?: string }) {
  const capability = CAPABILITY_META[permission.capability];
  const level = PERMISSION_LEVEL_META[permission.level];
  const CapabilityIcon = capability.icon;
  const LevelIcon = level.icon;
  const denied = permission.level === 'denied';

  return (
    <li className={cn('flex flex-wrap items-start gap-3 rounded-lg border border-line bg-surface p-3', denied && 'bg-surface-muted/50', className)}>
      <span className={cn('grid size-8 shrink-0 place-items-center rounded-md', denied ? 'bg-surface-muted text-fg-subtle' : 'bg-brand-soft text-brand-strong')}>
        <CapabilityIcon aria-hidden="true" className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn('text-sm font-medium', denied ? 'text-fg-muted' : 'text-fg')}>{capability.label}</p>
        <p className="text-xs text-fg-muted">{denied ? capability.description : permission.scope}</p>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={level.tone} icon={<LevelIcon aria-hidden="true" className="size-3" />}>
          {level.label}
        </Badge>
        {!denied && <RiskBadge level={permission.risk} />}
        {!denied && permission.requiresApproval && (
          <Badge tone="brand" icon={<UserCog aria-hidden="true" className="size-3" />}>
            Approval required
          </Badge>
        )}
      </div>
    </li>
  );
}
