import { SearchX } from 'lucide-react';
import { useNavigate, useParams } from 'react-router';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert } from '@/components/ui/Alert';
import { LinkButton } from '@/components/ui/Button';
import { toast } from '@/stores/toastStore';
import type { Agent } from '@/types/domain';
import { useAgent, useUpdateAgent } from './api';
import { useAgentPermissions } from './permissions';
import { AgentForm } from './form/AgentForm';
import { agentToFormValues, toAgentDraft } from './form/schema';

export default function EditAgentPage() {
  const { id = '' } = useParams();
  const query = useAgent(id);

  if (query.isPending) return <LoadingState label="Loading agent…" />;
  if (query.isError) return <ErrorState title="Agent could not be loaded" onRetry={() => void query.refetch()} retrying={query.isFetching} />;
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
  return <EditAgent agent={query.data} />;
}

function EditAgent({ agent }: { agent: Agent }) {
  const navigate = useNavigate();
  const update = useUpdateAgent(agent.id);
  const canUpdate = useAgentPermissions().canUpdate(agent);

  return (
    <>
      <PageHeader
        title={`Edit ${agent.name}`}
        breadcrumbs={[{ label: 'Agents', to: '/agents' }, { label: agent.name, to: `/agents/${agent.id}` }, { label: 'Edit' }]}
      />
      {!canUpdate && (
        <Alert tone="warning" title="Your role cannot change this agent" className="mb-6">
          Only its owner, an administrator or the organization owner can edit it. The API refuses
          this request regardless of what this page shows.
        </Alert>
      )}
      <DataNotice
        resource="agents"
        className="mb-6"
        demo="Changes are saved in this browser session only."
        live="Changes are saved to the AgentHub database."
      />
      <AgentForm
        key={agent.id}
        disabled={!canUpdate}
        defaultValues={agentToFormValues(agent)}
        submitLabel="Save changes"
        cancelTo={`/agents/${agent.id}`}
        submitting={update.isPending}
        onSubmit={(values) =>
          update.mutate(toAgentDraft(values), {
            onSuccess: (saved) => {
              toast.success('Changes saved', `${saved.name} was updated in this demo session.`);
              navigate(`/agents/${saved.id}`);
            },
            onError: (error) => toast.danger('Changes could not be saved', error.message),
          })
        }
      />
    </>
  );
}
