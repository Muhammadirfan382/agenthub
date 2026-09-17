import { OctagonX, Play } from 'lucide-react';
import { useState } from 'react';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { usePermission } from '@/features/auth/api';
import { useRuntimeState, useSetExecutionsPaused } from '@/features/executions/api';
import { formatDateTime } from '@/lib/format';
import { toast } from '@/stores/toastStore';
import type { RuntimeState } from '@/types/domain';

/**
 * The kill switch. Deliberately asymmetric: any administrator can stop
 * everything, but only the owner can start it again.
 */
export function RuntimeSettings() {
  const query = useRuntimeState();

  return (
    <QueryState
      query={query}
      loading={<LoadingState variant="inline" label="Loading runtime state…" />}
      errorTitle="Runtime state could not be loaded"
    >
      {(state) => <RuntimeControls state={state} />}
    </QueryState>
  );
}

function RuntimeControls({ state }: { state: RuntimeState }) {
  const permitted = usePermission();
  const setPaused = useSetExecutionsPaused();
  const [reason, setReason] = useState('');
  const [confirming, setConfirming] = useState(false);

  const canPause = permitted('runtime:pause');
  const canResume = permitted('runtime:resume');

  const engage = () =>
    setPaused.mutate(
      { paused: true, reason: reason.trim() || undefined },
      {
        onSuccess: () => {
          setConfirming(false);
          setReason('');
          toast.success('Executions stopped', 'Nothing new starts until this is released.');
        },
        onError: (error) => {
          setConfirming(false);
          toast.danger('Could not stop executions', error.message);
        },
      },
    );

  const release = () =>
    setPaused.mutate(
      { paused: false },
      {
        onSuccess: () => toast.success('Executions resumed'),
        onError: (error) => toast.danger('Could not resume executions', error.message),
      },
    );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Execution kill switch"
          description="Stops every execution in this organization and blocks new ones."
        />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-fg">
                Executions are {state.executionsPaused ? 'stopped' : 'running normally'}
              </p>
              {state.executionsPaused && (
                <p className="mt-0.5 text-xs text-fg-muted">
                  Engaged by {state.pausedBy ?? 'an administrator'}
                  {state.pausedAt ? ` on ${formatDateTime(state.pausedAt)}` : ''}
                  {state.reason ? `: ${state.reason}` : '.'}
                </p>
              )}
            </div>
            <Badge tone={state.executionsPaused ? 'danger' : 'success'}>
              {state.executionsPaused ? 'Stopped' : 'Running'}
            </Badge>
          </div>

          {state.executionsPaused ? (
            <>
              {!canResume && (
                <Alert tone="info" title="Only the owner can release this">
                  Stopping is an emergency action any administrator can take; starting again is the
                  owner's decision.
                </Alert>
              )}
              <Button
                variant="primary"
                disabled={!canResume}
                loading={setPaused.isPending}
                onClick={release}
              >
                <Play aria-hidden="true" className="size-4" />
                Resume executions
              </Button>
            </>
          ) : (
            <>
              {!canPause && (
                <Alert tone="info" title="Your role cannot stop executions">
                  Ask an administrator or the owner of this organization.
                </Alert>
              )}
              <Field label="Reason (optional)" hint="Recorded and shown to everyone who sees the banner.">
                {(control) => (
                  <Input
                    {...control}
                    value={reason}
                    disabled={!canPause}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="Investigating unexpected tool activity"
                  />
                )}
              </Field>
              <Button
                variant="danger"
                disabled={!canPause}
                loading={setPaused.isPending}
                onClick={() => setConfirming(true)}
              >
                <OctagonX aria-hidden="true" className="size-4" />
                Stop all executions
              </Button>
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="What the runtime does today"
          description="Being explicit about this matters more than the feature list."
        />
        <CardBody className="space-y-2 text-sm text-fg-muted">
          <p>
            The runtime orchestrates runs: it walks each step, holds them to the budget the agent
            declared, pauses for human approval and records everything.
          </p>
          <p>
            It <strong className="font-medium text-fg">executes nothing</strong>. There is no
            sandbox and no model gateway yet, so no agent code runs, no model is called and no tool
            is invoked. Runs are marked <code className="font-mono text-xs">simulation</code> and
            tool calls are recorded as simulated rather than succeeded.
          </p>
          {state.pendingApprovals > 0 && (
            <p className="text-fg">
              {state.pendingApprovals} step{state.pendingApprovals === 1 ? '' : 's'} currently
              waiting for approval.
            </p>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={confirming}
        tone="danger"
        title="Stop every execution?"
        description="Running executions are cancelled and new ones are refused until the owner releases this."
        confirmLabel="Stop executions"
        pending={setPaused.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={engage}
      />
    </div>
  );
}
