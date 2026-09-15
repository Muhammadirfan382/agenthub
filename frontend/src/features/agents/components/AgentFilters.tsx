import { LayoutGrid, List } from 'lucide-react';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { cn } from '@/lib/cn';
import type { AgentListParams, AgentSort } from '@/services/contracts';
import { AGENT_CATEGORIES, RISK_LEVELS } from '@/types/domain';

export type AgentView = 'table' | 'cards';

interface AgentFiltersProps {
  params: Required<AgentListParams>;
  onChange: (patch: Partial<AgentListParams>) => void;
  view: AgentView;
  onViewChange: (view: AgentView) => void;
}

const SORT_LABELS: Record<AgentSort, string> = {
  updated_desc: 'Recently updated',
  name_asc: 'Name (A–Z)',
  risk_desc: 'Highest risk',
  last_execution_desc: 'Last execution',
};

export function AgentFilters({ params, onChange, view, onViewChange }: AgentFiltersProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-3 shadow-card lg:flex-row lg:items-center">
      <SearchInput
        label="Search agents"
        placeholder="Search by name, tag or creator"
        value={params.search}
        onChange={(event) => onChange({ search: event.target.value })}
        className="lg:max-w-xs lg:flex-1"
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:flex lg:flex-1">
        <Select aria-label="Filter by status" value={params.status} onChange={(e) => onChange({ status: e.target.value as AgentListParams['status'] })}>
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="draft">Draft</option>
          <option value="disabled">Disabled</option>
        </Select>
        <Select aria-label="Filter by risk level" value={params.risk} onChange={(e) => onChange({ risk: e.target.value as AgentListParams['risk'] })}>
          <option value="all">All risk levels</option>
          {RISK_LEVELS.map((level) => (
            <option key={level} value={level}>
              {level[0]?.toUpperCase()}
              {level.slice(1)} risk
            </option>
          ))}
        </Select>
        <Select aria-label="Filter by category" value={params.category} onChange={(e) => onChange({ category: e.target.value as AgentListParams['category'] })}>
          <option value="all">All categories</option>
          {AGENT_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {CATEGORY_LABELS[category]}
            </option>
          ))}
        </Select>
        <Select aria-label="Sort agents" value={params.sort} onChange={(e) => onChange({ sort: e.target.value as AgentSort })}>
          {Object.entries(SORT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      <div role="group" aria-label="Layout" className="flex shrink-0 self-start rounded-md border border-line p-0.5 lg:self-auto">
        {(
          [
            { id: 'table', label: 'Table view', Icon: List },
            { id: 'cards', label: 'Card view', Icon: LayoutGrid },
          ] as const
        ).map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            aria-label={label}
            aria-pressed={view === id}
            onClick={() => onViewChange(id)}
            className={cn(
              'rounded p-1.5 focus-visible:outline-2 focus-visible:outline-ring',
              view === id ? 'bg-surface-hover text-fg' : 'text-fg-subtle hover:text-fg',
            )}
          >
            <Icon aria-hidden="true" className="size-4" />
          </button>
        ))}
      </div>
    </div>
  );
}
