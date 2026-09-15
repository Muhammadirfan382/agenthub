import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { toast } from '@/stores/toastStore';
import type { UserProfile } from '@/types/domain';
import { useCurrentUser, useUpdateProfile } from '../api';

const TIMEZONES = ['UTC', 'Europe/London', 'Europe/Berlin', 'America/New_York', 'America/Los_Angeles', 'Asia/Karachi', 'Asia/Singapore', 'Australia/Sydney'];

const profileSchema = z.object({
  name: z.string().trim().min(2, 'Name must be at least 2 characters.').max(80, 'Name must be 80 characters or fewer.'),
  email: z.email('Enter a valid email address.').max(254),
  timezone: z.string().refine((value) => TIMEZONES.includes(value), 'Choose a time zone.'),
});

type ProfileValues = z.infer<typeof profileSchema>;

export function ProfileSettings() {
  const query = useCurrentUser();
  return (
    <QueryState query={query} loading={<LoadingState variant="inline" label="Loading profile…" />} errorTitle="Profile could not be loaded">
      {(user) => <ProfileForm key={user.id} user={user} />}
    </QueryState>
  );
}

function ProfileForm({ user }: { user: UserProfile }) {
  const update = useUpdateProfile();
  const { register, handleSubmit, formState } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: user.name, email: user.email, timezone: user.timezone },
  });

  const onSubmit = handleSubmit((values) =>
    update.mutate(values, {
      onSuccess: () => toast.success('Profile saved', 'Stored in this demo session only.'),
      onError: (error) => toast.danger('Profile could not be saved', error.message),
    }),
  );

  return (
    <Card>
      <CardHeader title="Profile" description="Demo profile. Real accounts arrive with authentication (Phase 3)." />
      <CardBody>
        <form noValidate onSubmit={onSubmit} aria-label="Profile" className="space-y-5">
          <Field label="Full name" required error={formState.errors.name?.message}>
            {(control) => <Input {...control} {...register('name')} autoComplete="name" />}
          </Field>
          <Field label="Email" required error={formState.errors.email?.message}>
            {(control) => <Input {...control} {...register('email')} type="email" autoComplete="email" />}
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
          <p className="text-xs text-fg-subtle">Role: {user.role}</p>
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
