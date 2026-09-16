import { useNavigate } from 'react-router';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { PageHeader } from '@/components/layout/PageHeader';
import { toast } from '@/stores/toastStore';
import { useCreateAgent } from './api';
import { AgentForm } from './form/AgentForm';
import { defaultAgentFormValues, toAgentDraft } from './form/schema';

export default function CreateAgentPage() {
  const navigate = useNavigate();
  const create = useCreateAgent();

  return (
    <>
      <PageHeader
        title="Create agent"
        description="Configure identity, model, tools, permissions, limits and security policy."
        breadcrumbs={[{ label: 'Agents', to: '/agents' }, { label: 'Create agent' }]}
      />
      <DataNotice
        resource="agents"
        className="mb-6"
        demo="The agent is saved in this browser session only. Nothing is sent to a backend and the agent cannot run yet."
        live="The agent is saved to the AgentHub database. Permissions here are configuration only: no runtime enforces them yet."
      />
      <AgentForm
        defaultValues={defaultAgentFormValues}
        submitLabel="Create agent"
        cancelTo="/agents"
        submitting={create.isPending}
        onSubmit={(values) =>
          create.mutate(toAgentDraft(values), {
            onSuccess: (agent) => {
              toast.success(`${agent.name} created`, 'Saved as a draft in this demo session.');
              navigate(`/agents/${agent.id}`);
            },
            onError: (error) => toast.danger('Agent could not be created', error.message),
          })
        }
      />
    </>
  );
}
