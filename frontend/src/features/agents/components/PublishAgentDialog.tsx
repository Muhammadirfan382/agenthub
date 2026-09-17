import { useState } from 'react';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { toast } from '@/stores/toastStore';
import { type Agent, VISIBILITY_LABELS, type Visibility } from '@/types/domain';
import { usePublishAgent } from '../api';

const VISIBILITY_HINT: Record<Visibility, string> = {
  private: 'Nobody else sees it. It stays out of the marketplace.',
  organization: 'Listed in the marketplace for your organization only.',
  public: 'Listed for every organization on this AgentHub.',
};

/**
 * Publishing freezes the agent's current configuration as an immutable
 * version. Later edits change the next version, never this one.
 */
export function PublishAgentDialog({
  agent,
  open,
  onClose,
}: {
  agent: Agent;
  open: boolean;
  onClose: () => void;
}) {
  const publish = usePublishAgent(agent.id);
  const [changelog, setChangelog] = useState('');
  const [visibility, setVisibility] = useState<Visibility>(agent.visibility);

  const submit = () => {
    const entries = changelog
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length >= 3);

    publish.mutate(
      { changelog: entries, visibility },
      {
        onSuccess: (version) => {
          onClose();
          setChangelog('');
          toast.success(
            `v${version.version} published`,
            visibility === 'private'
              ? 'Not listed in the marketplace.'
              : `Listed for ${visibility === 'public' ? 'every organization' : 'your organization'}.`,
          );
        },
        onError: (error) => toast.danger('Could not publish', error.message),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Publish v${agent.version}`}
      description="The configuration is frozen as it is now. Raise the version number to publish again."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={publish.isPending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={publish.isPending}>
            Publish version
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="What changed" hint="One line per change. Optional.">
          {(control) => (
            <Textarea
              {...control}
              value={changelog}
              onChange={(event) => setChangelog(event.target.value)}
              placeholder={'Tighter source allow-list\nAdded document reader tool'}
            />
          )}
        </Field>

        <Field label="Marketplace visibility" hint={VISIBILITY_HINT[visibility]}>
          {(control) => (
            <Select
              {...control}
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as Visibility)}
            >
              {(Object.keys(VISIBILITY_LABELS) as Visibility[]).map((option) => (
                <option key={option} value={option}>
                  {VISIBILITY_LABELS[option]}
                </option>
              ))}
            </Select>
          )}
        </Field>

        {visibility === 'public' && (
          <Alert tone="warning" title="Anyone here can install it">
            Other organizations will see this manifest and can install the agent, granting it only
            what they choose.
          </Alert>
        )}
      </div>
    </Dialog>
  );
}
