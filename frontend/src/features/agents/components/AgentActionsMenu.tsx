import { Ellipsis, Eye, Pencil, Play, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router';
import { DropdownMenu, type MenuItem } from '@/components/ui/DropdownMenu';
import { useAgentPermissions } from '../permissions';
import type { Agent } from '@/types/domain';

interface AgentActionsMenuProps {
  agent: Agent;
  onExecute: (agent: Agent) => void;
  onDelete: (agent: Agent) => void;
}

export function AgentActionsMenu({ agent, onExecute, onDelete }: AgentActionsMenuProps) {
  const navigate = useNavigate();
  const permissions = useAgentPermissions();
  const active = agent.status === 'active';

  // Actions the role cannot perform are left out rather than shown failing.
  const items: MenuItem[] = [
    { id: 'view', label: 'View', icon: Eye, onSelect: () => navigate(`/agents/${agent.id}`) },
  ];
  if (permissions.canUpdate(agent)) {
    items.push({
      id: 'edit',
      label: 'Edit',
      icon: Pencil,
      onSelect: () => navigate(`/agents/${agent.id}/edit`),
    });
  }
  if (permissions.canExecute(agent)) {
    items.push({
      id: 'execute',
      label: active ? 'Execute' : 'Execute (agent not active)',
      icon: Play,
      disabled: !active,
      onSelect: () => onExecute(agent),
    });
  }
  if (permissions.canDelete(agent)) {
    items.push({
      id: 'delete',
      label: 'Delete',
      icon: Trash2,
      tone: 'danger',
      onSelect: () => onDelete(agent),
    });
  }

  return (
    <DropdownMenu
      label={`Actions for ${agent.name}`}
      trigger={<Ellipsis aria-hidden="true" className="size-4" />}
      items={items}
    />
  );
}
