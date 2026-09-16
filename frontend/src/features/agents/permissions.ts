import { useCurrentSession, usePermission } from '@/features/auth/api';
import type { Agent } from '@/types/domain';

/**
 * What the signed-in user may do with an agent, mirroring the backend rules:
 * administrators and owners manage every agent in the organization, a member
 * manages the agents they own, and a viewer manages none.
 *
 * Used to hide controls that would fail. The API enforces the same rules.
 */
export function useAgentPermissions() {
  const session = useCurrentSession();
  const permitted = usePermission();
  const owns = (agent: Agent) => agent.owner.id === session?.user.id;

  return {
    canCreate: permitted('agent:create'),
    canUpdate: (agent: Agent) => permitted('agent:update', { ownsResource: owns(agent) }),
    canDelete: (agent: Agent) => permitted('agent:delete', { ownsResource: owns(agent) }),
    canExecute: (agent: Agent) => permitted('agent:execute', { ownsResource: owns(agent) }),
  };
}
