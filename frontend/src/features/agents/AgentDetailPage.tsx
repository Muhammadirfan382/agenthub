import { Ellipsis, Pencil, Play, Power, Rocket, SearchX, Trash2, Upload } from 'lucide-react';
import { useId, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { PageHeader } from '@/components/layout/PageHeader';
import { AgentStatusBadge, RiskBadge, VerificationBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DropdownMenu } from '@/components/ui/DropdownMenu';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import { toast } from '@/stores/toastStore';
import { type Agent, VISIBILITY_LABELS } from '@/types/domain';
import { useAgent } from './api';
import { AgentCapabilitiesTab } from './detail/AgentCapabilitiesTab';
import { AgentExecutionsTab } from './detail/AgentExecutionsTab';
import { AgentOverviewTab } from './detail/AgentOverviewTab';
import { AgentSecurityTab } from './detail/AgentSecurityTab';
import { AgentVersionsTab } from './detail/AgentVersionsTab';
import { PublishAgentDialog } from './components/PublishAgentDialog';
import { useAgentPermissions } from './permissions';
import { useAgentActions } from './useAgentActions';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'capabilities', label: 'Capabilities' },
  { id: 'versions', label: 'Versions' },
  { id: 'security', label: 'Security' },
  { id: 'executions', label: 'Executions' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function AgentDetailPage() {
  const { id = '' } = useParams();
  const query = useAgent(id);

  if (query.isPending) return <LoadingState label="Loading agent…" />;
  if (query.isError) {
    return <ErrorState title="Agent could not be loaded" onRetry={() => void query.refetch()} retrying={query.isFetching} />;
  }
  if (!query.data) {
    return (
      <EmptyState
        icon={SearchX}
        title="Agent not found"
        description="This agent does not exist or has been deleted."
        action={
          <LinkButton to="/agents" variant="primary" size="sm">
            Back to agents
          </LinkButton>
        }
      />
    );
  }
  return <AgentDetail agent={query.data} />;
}

function AgentDetail({ agent }: { agent: Agent }) {
  const navigate = useNavigate();
  const idPrefix = useId();
  const [searchParams, setSearchParams] = useSearchParams();
  const [deployOpen, setDeployOpen] = useState(false);
  const actions = useAgentActions({ onDeleted: () => navigate('/agents') });
  const permissions = useAgentPermissions();
  const [publishOpen, setPublishOpen] = useState(false);

  const requestedTab = searchParams.get('tab');
  const tab: TabId = TABS.some((t) => t.id === requestedTab) ? (requestedTab as TabId) : 'overview';
  const setTab = (next: TabId) => setSearchParams(next === 'overview' ? {} : { tab: next }, { replace: true });

  const deploy = () => {
    setDeployOpen(false);
    toast.info('Deployment not available yet', `v${agent.version} was not deployed. Deployment arrives with the agent runtime (Phase 5).`);
  };

  return (
    <>
      <PageHeader
        title={agent.name}
        description={agent.description}
        breadcrumbs={[{ label: 'Agents', to: '/agents' }, { label: agent.name }]}
        meta={
          <>
            <AgentStatusBadge status={agent.status} />
            <VerificationBadge status={agent.verification} />
            <RiskBadge level={agent.riskLevel} />
            <Badge>v{agent.version}</Badge>
            <Badge>{CATEGORY_LABELS[agent.category]}</Badge>
            <Badge tone={agent.visibility === 'private' ? 'neutral' : 'brand'}>
              {VISIBILITY_LABELS[agent.visibility]}
            </Badge>
          </>
        }
        actions={
          <>
            {permissions.canExecute(agent) && (
              <Button variant="primary" onClick={() => actions.requestExecute(agent)} disabled={agent.status !== 'active'}>
                <Play aria-hidden="true" className="size-4" />
                Execute
              </Button>
            )}
            {permissions.canUpdate(agent) && (
              <>
                <Button variant="secondary" onClick={() => setPublishOpen(true)}>
                  <Upload aria-hidden="true" className="size-4" />
                  Publish
                </Button>
                <LinkButton to={`/agents/${agent.id}/edit`} variant="secondary">
                  <Pencil aria-hidden="true" className="size-4" />
                  Edit
                </LinkButton>
                <Button variant="secondary" onClick={() => setDeployOpen(true)} disabled={agent.status === 'disabled'}>
                  <Rocket aria-hidden="true" className="size-4" />
                  Deploy
                </Button>
                <Button variant="secondary" onClick={() => actions.toggleDisabled(agent)} loading={actions.statusPending}>
                  {!actions.statusPending && <Power aria-hidden="true" className="size-4" />}
                  {agent.status === 'disabled' ? 'Enable' : 'Disable'}
                </Button>
              </>
            )}
            {permissions.canDelete(agent) && (
              <DropdownMenu
                label={`More actions for ${agent.name}`}
                trigger={<Ellipsis aria-hidden="true" className="size-4" />}
                items={[{ id: 'delete', label: 'Delete agent', icon: Trash2, tone: 'danger', onSelect: () => actions.requestDelete(agent) }]}
              />
            )}
          </>
        }
      />

      {agent.status !== 'active' && (
        <p className="mb-4 text-sm text-fg-muted">
          Execution is only available for active agents. This agent is <strong className="font-medium text-fg">{agent.status}</strong>.
        </p>
      )}

      <Tabs label="Agent details" idPrefix={idPrefix} items={[...TABS]} value={tab} onChange={setTab} />
      <TabPanel idPrefix={idPrefix} id={tab} className="pt-6">
        {tab === 'overview' && <AgentOverviewTab agent={agent} />}
        {tab === 'capabilities' && <AgentCapabilitiesTab agent={agent} />}
        {tab === 'versions' && <AgentVersionsTab agent={agent} />}
        {tab === 'security' && <AgentSecurityTab agent={agent} />}
        {tab === 'executions' && <AgentExecutionsTab agent={agent} />}
      </TabPanel>

      <ConfirmDialog
        open={deployOpen}
        title={`Deploy ${agent.name} v${agent.version}?`}
        description="Deployment is a frontend workflow preview. No deployment happens until the agent runtime exists."
        confirmLabel="Continue"
        onConfirm={deploy}
        onCancel={() => setDeployOpen(false)}
      />
      {actions.dialogs}
      <PublishAgentDialog agent={agent} open={publishOpen} onClose={() => setPublishOpen(false)} />
    </>
  );
}
