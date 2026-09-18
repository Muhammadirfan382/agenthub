import { useState } from 'react';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Textarea } from '@/components/ui/Textarea';
import { toast } from '@/stores/toastStore';
import type { Agent } from '@/types/domain';
import { useDeleteAgent, useRequestExecution, useSetAgentStatus } from './api';

type PendingAction = { kind: 'execute' | 'delete'; agent: Agent } | null;

interface Options {
  onDeleted?: (agent: Agent) => void;
}

/**
 * Shared agent actions for list and detail pages. Each action goes through the
 * service layer, so Phase 2 only has to swap the service implementation.
 * Nothing here is an authorization check: the backend decides in Phase 3.
 */
export function useAgentActions({ onDeleted }: Options = {}) {
  const [pending, setPending] = useState<PendingAction>(null);
  const [task, setTask] = useState('');
  const execute = useRequestExecution();
  const remove = useDeleteAgent();
  const setStatus = useSetAgentStatus();

  const close = () => {
    setPending(null);
    setTask('');
  };

  const confirmExecute = (agent: Agent) => {
    execute.mutate({ id: agent.id, input: task.trim() || undefined }, {
      onSuccess: (execution) => {
        toast.success('Run queued', `${execution.id} is queued. Follow it on the execution page.`);
        close();
      },
      onError: (error) => {
        toast.danger('Execution could not be requested', error.message);
        close();
      },
    });
  };

  const confirmDelete = (agent: Agent) => {
    remove.mutate(agent.id, {
      onSuccess: () => {
        toast.success(`${agent.name} deleted`, 'Removed from this demo session only.');
        close();
        onDeleted?.(agent);
      },
      onError: (error) => {
        toast.danger('Agent could not be deleted', error.message);
        close();
      },
    });
  };

  const toggleDisabled = (agent: Agent) => {
    const next = agent.status === 'disabled' ? 'paused' : 'disabled';
    setStatus.mutate(
      { id: agent.id, status: next },
      {
        onSuccess: () => toast.success(next === 'disabled' ? `${agent.name} disabled` : `${agent.name} re-enabled (paused)`),
        onError: (error) => toast.danger('Status could not be changed', error.message),
      },
    );
  };

  const dialogs = (
    <>
      <ConfirmDialog
        open={pending?.kind === 'execute'}
        title={pending ? `Run ${pending.agent.name}?` : 'Run agent?'}
        description="A real model answers if one is configured for this agent's tier; otherwise the run is simulated. Tools the model asks for are checked against this agent's permissions but never executed."
        confirmLabel="Start run"
        pending={execute.isPending}
        onConfirm={() => pending && confirmExecute(pending.agent)}
        onCancel={close}
      >
        <Field label="Task (optional)" hint="Sent to the model as your request. Up to 8,000 characters.">
          {(control) => (
            <Textarea
              {...control}
              value={task}
              maxLength={8000}
              rows={4}
              onChange={(event) => setTask(event.target.value)}
              placeholder="Summarise last night's failed logins."
            />
          )}
        </Field>
      </ConfirmDialog>
      <ConfirmDialog
        open={pending?.kind === 'delete'}
        tone="danger"
        title={pending ? `Delete ${pending.agent.name}?` : 'Delete agent?'}
        description="This removes the agent from the current demo session. In a real workspace, deletion will be permanent."
        confirmLabel="Delete agent"
        pending={remove.isPending}
        onConfirm={() => pending && confirmDelete(pending.agent)}
        onCancel={close}
      />
    </>
  );

  return {
    requestExecute: (agent: Agent) => setPending({ kind: 'execute', agent }),
    requestDelete: (agent: Agent) => setPending({ kind: 'delete', agent }),
    toggleDisabled,
    statusPending: setStatus.isPending,
    dialogs,
  };
}
