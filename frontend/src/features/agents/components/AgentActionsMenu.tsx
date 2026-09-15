import { Ellipsis, Eye, Pencil, Play, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router';
import { DropdownMenu } from '@/components/ui/DropdownMenu';
import type { Agent } from '@/types/domain';

interface AgentActionsMenuProps {
  agent: Agent;
  onExecute: (agent: Agent) => void;
  onDelete: (agent: Agent) => void;
}

export function AgentActionsMenu({ agent, onExecute, onDelete }: AgentActionsMenuProps) {
  const navigate = useNavigate();
  const canExecute = agent.status === 'active';
  return (
    <DropdownMenu
      label={`Actions for ${agent.name}`}
      trigger={<Ellipsis aria-hidden="true" className="size-4" />}
      items={[
        { id: 'view', label: 'View', icon: Eye, onSelect: () => navigate(`/agents/${agent.id}`) },
        { id: 'edit', label: 'Edit', icon: Pencil, onSelect: () => navigate(`/agents/${agent.id}/edit`) },
        {
          id: 'execute',
          label: canExecute ? 'Execute' : 'Execute (agent not active)',
          icon: Play,
          disabled: !canExecute,
          onSelect: () => onExecute(agent),
        },
        { id: 'delete', label: 'Delete', icon: Trash2, tone: 'danger', onSelect: () => onDelete(agent) },
      ]}
    />
  );
}
