import type { Role } from '@/types/domain';

/**
 * The same permission matrix the backend enforces, mirrored here so the UI can
 * hide controls a user cannot use.
 *
 * This is presentation only. Hiding a button is a courtesy, not a security
 * control: every one of these actions is checked again server-side, and the
 * API refuses it whatever the UI shows.
 */
export type PermissionAction =
  | 'agent:read'
  | 'agent:create'
  | 'agent:update'
  | 'agent:delete'
  | 'agent:execute'
  | 'agent:publish'
  | 'execution:read'
  | 'installation:read'
  | 'installation:manage'
  | 'runtime:pause'
  | 'runtime:resume'
  | 'member:read'
  | 'member:manage'
  | 'organization:manage'
  | 'audit:read';

const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

const MINIMUM_ROLE: Record<PermissionAction, Role> = {
  'agent:read': 'viewer',
  'execution:read': 'viewer',
  'member:read': 'viewer',
  'installation:read': 'viewer',
  'agent:create': 'member',
  'agent:update': 'admin',
  'agent:delete': 'admin',
  'agent:execute': 'admin',
  'agent:publish': 'admin',
  'member:manage': 'admin',
  'installation:manage': 'admin',
  // Stopping everything is an emergency any administrator can trigger;
  // releasing it again is the owner's call.
  'runtime:pause': 'admin',
  'runtime:resume': 'owner',
  'organization:manage': 'owner',
  // Who did what is sensitive in itself: members and viewers do not see it.
  'audit:read': 'admin',
};

/** Actions a member may also perform on an agent they own. */
const OWNER_ACTIONS: readonly PermissionAction[] = [
  'agent:update',
  'agent:delete',
  'agent:execute',
  'agent:publish',
];

export function hasRole(role: Role, minimum: Role): boolean {
  return RANK[role] >= RANK[minimum];
}

export function can(
  role: Role | undefined,
  action: PermissionAction,
  options: { ownsResource?: boolean } = {},
): boolean {
  if (!role) return false;
  if (hasRole(role, MINIMUM_ROLE[action])) return true;
  if (options.ownsResource && OWNER_ACTIONS.includes(action)) return hasRole(role, 'member');
  return false;
}
