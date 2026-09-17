import { permissionRisk } from '@/lib/risk';
import type { CapabilityKey, PermissionGrant, PermissionLevel } from '@/types/domain';

/** The editable form of one grant, before it is sent. */
export interface GrantDraft {
  level: PermissionLevel;
  scope: string;
  requiresApproval: boolean;
}

export type GrantState = Partial<Record<CapabilityKey, GrantDraft>>;

/** Nothing is granted until someone chooses to grant it. */
export function emptyGrants(): GrantState {
  return {};
}

export function grantsFrom(grants: PermissionGrant[]): GrantState {
  const state: GrantState = {};
  for (const grant of grants) {
    if (grant.level === 'denied') continue;
    state[grant.capability] = {
      level: grant.level,
      scope: grant.scope,
      requiresApproval: grant.requiresApproval,
    };
  }
  return state;
}

/** Only granted capabilities are sent; the backend denies everything else. */
export function toGrantList(state: GrantState): PermissionGrant[] {
  return Object.entries(state)
    .filter(([, draft]) => draft && draft.level !== 'denied')
    .map(([capability, draft]) => ({
      capability: capability as CapabilityKey,
      level: draft.level,
      requiresApproval: draft.requiresApproval,
      scope: draft.scope,
      // Recomputed by the server; sent only to satisfy the shape.
      risk: permissionRisk(capability as CapabilityKey, draft.level),
    }));
}
