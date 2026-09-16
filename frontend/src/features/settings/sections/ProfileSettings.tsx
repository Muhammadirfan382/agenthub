import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useCurrentSession, useUpdateProfile } from '@/features/auth/api';
import { useServices } from '@/services/ServicesContext';
import { toast } from '@/stores/toastStore';
import { ROLE_LABELS, type SessionInfo } from '@/types/domain';

const TIMEZONES = [
  'UTC',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Karachi',
  'Asia/Singapore',
  'Australia/Sydney',
];

const profileSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, 'Name must be at least 2 characters.')
    .max(80, 'Name must be 80 characters or fewer.'),
  timezone: z.string().refine((value) => TIMEZONES.includes(value), 'Choose a time zone.'),
});

type ProfileValues = z.infer<typeof profileSchema>;

export function ProfileSettings() {
  const session = useCurrentSession();
  if (!session) return null;
  return <ProfileForm key={session.user.id} session={session} />;
}

function ProfileForm({ session }: { session: SessionInfo }) {
  const { dataSource } = useServices();
  const update = useUpdateProfile();
  const { user } = session;
  const { register, handleSubmit, formState } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: user.name, timezone: user.timezone },
  });

  const onSubmit = handleSubmit((values) =>
    update.mutate(values, {
      onSuccess: () =>
        toast.success(
          'Profile saved',
          dataSource === 'demo' ? 'Stored in this demo session only.' : 'Saved to your account.',
        ),
      onError: (error) => toast.danger('Profile could not be saved', error.message),
    }),
  );

  return (
    <Card>
      <CardHeader
        title="Profile"
        description={`Signed in to ${session.organization.name} as ${ROLE_LABELS[session.role]}.`}
      />
      <CardBody>
        <form noValidate onSubmit={onSubmit} aria-label="Profile" className="space-y-5">
          <Field label="Full name" required error={formState.errors.name?.message}>
            {(control) => <Input {...control} {...register('name')} autoComplete="name" />}
          </Field>
          <Field
            label="Email"
            hint="Changing the address on an account needs a verification flow, which does not exist yet."
          >
            {(control) => (
              <Input {...control} value={user.email} readOnly disabled autoComplete="email" />
            )}
          </Field>
          <Field label="Time zone" required error={formState.errors.timezone?.message}>
            {(control) => (
              <Select {...control} {...register('timezone')}>
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <p className="text-xs text-fg-subtle">
            Your role is set by an administrator of this organization.
          </p>
          <div className="flex justify-end">
            <Button type="submit" loading={update.isPending}>
              Save profile
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
