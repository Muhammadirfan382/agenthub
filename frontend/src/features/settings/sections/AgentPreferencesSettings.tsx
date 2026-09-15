import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Checkbox } from '@/components/ui/Checkbox';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { MODEL_OPTIONS } from '@/features/agents/form/schema';
import { toast } from '@/stores/toastStore';

const preferencesSchema = z.object({
  defaultModel: z.string().refine((value) => MODEL_OPTIONS.some((m) => m.value === value), 'Choose a model.'),
  defaultMaxRuntimeSeconds: z
    .number({ error: 'Enter a number.' })
    .int('Use a whole number.')
    .min(10, 'Must be at least 10 seconds.')
    .max(3600, 'Must be at most 3600 seconds.'),
  requireApprovalForHighRisk: z.boolean(),
  strictSandboxByDefault: z.boolean(),
});

type Preferences = z.infer<typeof preferencesSchema>;

export function AgentPreferencesSettings() {
  const { register, handleSubmit, formState } = useForm<Preferences>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: { defaultModel: 'balanced-large', defaultMaxRuntimeSeconds: 300, requireApprovalForHighRisk: true, strictSandboxByDefault: true },
  });

  return (
    <Card>
      <CardHeader title="Agent preferences" description="Defaults for new agents. Not saved yet (demo)." />
      <CardBody>
        <form
          noValidate
          aria-label="Agent preferences"
          onSubmit={handleSubmit(() => toast.info('Preferences not saved', 'Agent defaults will be stored server-side in a later phase.'))}
          className="space-y-5"
        >
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Default model" required error={formState.errors.defaultModel?.message}>
              {(control) => (
                <Select {...control} {...register('defaultModel')}>
                  {MODEL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Default max runtime (seconds)" required hint="10 to 3,600." error={formState.errors.defaultMaxRuntimeSeconds?.message}>
              {(control) => <Input {...control} {...register('defaultMaxRuntimeSeconds', { valueAsNumber: true })} type="number" min={10} max={3600} />}
            </Field>
          </div>
          <Checkbox label="Require approval for high-risk actions" description="Recommended. Applies to new agents." {...register('requireApprovalForHighRisk')} />
          <Checkbox label="Use the strict sandbox by default" {...register('strictSandboxByDefault')} />
          <div className="flex justify-end">
            <Button type="submit">Save preferences</Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
