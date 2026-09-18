import { OctagonX, Play, ShieldCheck } from 'lucide-react';
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
import {
  useCheckSandbox,
  useRuntimeState,
  useSandboxStatus,
  useSetExecutionsPaused,
} from '@/features/executions/api';
import { SandboxChecks } from '@/features/executions/components/SandboxChecks';
import { formatDateTime } from '@/lib/format';
import { toast } from '@/stores/toastStore';
import type { RuntimeState, SandboxReport, SandboxStatus } from '@/types/domain';

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

      <SandboxSettings />

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
            Before a run starts, it creates an isolated container and checks it. A run is marked{' '}
            <code className="font-mono text-xs">sandbox</code> only when every isolation check
            passes; a container that fails a check fails the run. Without a container runtime, runs
            are marked <code className="font-mono text-xs">simulation</code>.
          </p>
          <p>
            Either way it <strong className="font-medium text-fg">executes nothing</strong>. There
            is no model gateway yet, so no agent code runs inside the container, no model is called
            and no tool is invoked. Tool calls are recorded as simulated rather than succeeded.
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

/** The box runs are given, and a way to check that it holds. */
function SandboxSettings() {
  const query = useSandboxStatus();

  return (
    <Card>
      <CardHeader
        title="Execution sandbox"
        description="The isolated container each run is given before anything else happens."
      />
      <CardBody>
        <QueryState
          query={query}
          loading={<LoadingState variant="inline" label="Loading sandbox status…" />}
          errorTitle="Sandbox status could not be loaded"
        >
          {(status) => <SandboxControls status={status} />}
        </QueryState>
      </CardBody>
    </Card>
  );
}

function sandboxState(status: SandboxStatus): { label: string; tone: 'success' | 'warning' | 'neutral' } {
  if (!status.enabled) return { label: 'Switched off', tone: 'neutral' };
  if (status.available) return { label: 'Runtime available', tone: 'success' };
  return { label: 'No runtime', tone: 'warning' };
}

function SandboxControls({ status }: { status: SandboxStatus }) {
  const permitted = usePermission();
  const check = useCheckSandbox();
  const [report, setReport] = useState<SandboxReport | null>(null);
  const canCheck = permitted('runtime:pause');
  const state = sandboxState(status);

  const runCheck = () =>
    check.mutate(undefined, {
      onSuccess: (result) => {
        setReport(result.report);
        if (result.report?.passed) toast.success('Sandbox verified', result.report.summary);
        else toast.danger('The sandbox could not be verified', result.detail);
      },
      onError: (error) => toast.danger('Could not run the isolation check', error.message),
    });

  const limits: [string, string][] = [
    ['Image', status.image],
    ['Runtime command', status.command],
    ['Memory', `${status.memoryMb} MB, no swap`],
    ['CPU', `${status.cpus} ${status.cpus === 1 ? 'core' : 'cores'}`],
    ['Processes', String(status.pidsLimit)],
    ['Scratch space', `${status.tmpfsMb} MB, not executable`],
    ['Time limit', `${status.timeoutSeconds}s`],
    ['Network', 'None'],
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted">{status.detail}</p>
        <Badge tone={state.tone}>{state.label}</Badge>
      </div>

      {status.required ? (
        <Alert tone="info" title="Runs require a verified sandbox">
          A run that cannot get an isolated container is refused rather than simulated.
        </Alert>
      ) : (
        !status.available && (
          <Alert tone="warning" title="Runs are not isolated here">
            Without a container runtime, runs are recorded as simulations. Set{' '}
            <code className="font-mono text-xs">REQUIRE_SANDBOX=true</code> to refuse them instead.
          </Alert>
        )
      )}

      <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
        {limits.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-xs text-fg-subtle">{label}</dt>
            <dd className="text-sm break-words text-fg">{value}</dd>
          </div>
        ))}
      </dl>

      {!canCheck && (
        <Alert tone="info" title="Your role cannot start containers">
          Running the isolation check is an administrator action.
        </Alert>
      )}
      <Button variant="secondary" disabled={!canCheck} loading={check.isPending} onClick={runCheck}>
        <ShieldCheck aria-hidden="true" className="size-4" />
        Run isolation check
      </Button>

      {report && <SandboxChecks report={report} />}
    </div>
  );
}
