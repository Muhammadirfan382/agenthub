import { Bot, Plus, SearchX } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, LinkButton } from '@/components/ui/Button';
import type { AgentListParams, AgentSort } from '@/services/contracts';
import { useAgents } from './api';
import { AgentCard } from './components/AgentCard';
import { AgentFilters, type AgentView } from './components/AgentFilters';
import { AgentTable } from './components/AgentTable';
import { useAgentActions } from './useAgentActions';

const DEFAULTS: Required<AgentListParams> = { search: '', status: 'all', risk: 'all', category: 'all', sort: 'updated_desc' };

function readParams(searchParams: URLSearchParams): Required<AgentListParams> {
  return {
    search: searchParams.get('q') ?? DEFAULTS.search,
    status: (searchParams.get('status') as AgentListParams['status']) ?? DEFAULTS.status,
    risk: (searchParams.get('risk') as AgentListParams['risk']) ?? DEFAULTS.risk,
    category: (searchParams.get('category') as AgentListParams['category']) ?? DEFAULTS.category,
    sort: (searchParams.get('sort') as AgentSort) ?? DEFAULTS.sort,
  };
}

export default function AgentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useState<AgentView>('table');
  const params = readParams(searchParams);
  const query = useAgents(params);
  const actions = useAgentActions();

  const update = (patch: Partial<AgentListParams>) => {
    const next = { ...params, ...patch };
    const urlKeys: Record<keyof AgentListParams, string> = { search: 'q', status: 'status', risk: 'risk', category: 'category', sort: 'sort' };
    const out = new URLSearchParams();
    (Object.keys(urlKeys) as (keyof AgentListParams)[]).forEach((key) => {
      if (next[key] !== DEFAULTS[key]) out.set(urlKeys[key], String(next[key]));
    });
    setSearchParams(out, { replace: true });
  };

  const filtersActive = JSON.stringify({ ...params, sort: DEFAULTS.sort }) !== JSON.stringify(DEFAULTS);

  return (
    <>
      <PageHeader
        title="Agents"
        description="Manage the agents in your workspace: their status, versions, verification and risk."
        actions={
          <LinkButton to="/agents/create" variant="primary">
            <Plus aria-hidden="true" className="size-4" />
            Create agent
          </LinkButton>
        }
      />

      <DataNotice
        resource="agents"
        className="mb-4"
        demo="Agents shown here are demonstration data. Create, edit, execute and delete change only this browser session."
        live="Agents are stored in the AgentHub database. They cannot run yet: requesting an execution records a queued row and nothing else."
      />

      <AgentFilters params={params} onChange={update} view={view} onViewChange={setView} />

      <div className="mt-4">
        <QueryState
          query={query}
          loading={<LoadingState variant={view === 'table' ? 'table' : 'cards'} label="Loading agents…" />}
          errorTitle="Agents could not be loaded"
          isEmpty={(agents) => agents.length === 0}
          empty={
            filtersActive ? (
              <EmptyState
                icon={SearchX}
                title="No agents match your filters"
                description="Try a different search term or clear the filters."
                action={
                  <Button variant="secondary" size="sm" onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}>
                    Clear filters
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={Bot}
                title="No agents yet"
                description="Create your first agent to start managing it here."
                action={
                  <LinkButton to="/agents/create" variant="primary" size="sm">
                    Create agent
                  </LinkButton>
                }
              />
            )
          }
        >
          {(agents) => (
            <>
              <p aria-live="polite" className="mb-3 text-sm text-fg-muted">
                {agents.length} {agents.length === 1 ? 'agent' : 'agents'}
              </p>
              {view === 'table' ? (
                <AgentTable
                  agents={agents}
                  sort={params.sort}
                  onSortChange={(sort) => update({ sort })}
                  onExecute={actions.requestExecute}
                  onDelete={actions.requestDelete}
                />
              ) : (
                <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {agents.map((agent) => (
                    <li key={agent.id}>
                      <AgentCard agent={agent} onExecute={actions.requestExecute} onDelete={actions.requestDelete} />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </QueryState>
      </div>

      {actions.dialogs}
    </>
  );
}
