import { zodResolver } from '@hookform/resolvers/zod';
import { KeyRound, Monitor } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { useChangePassword, useCurrentSession } from '@/features/auth/api';
import { formatDateTime } from '@/lib/format';
import { useServices } from '@/services/ServicesContext';
import { toast } from '@/stores/toastStore';

// Mirrors the backend rule: length, not composition.
const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Enter your current password.'),
    newPassword: z
      .string()
      .min(12, 'Use at least 12 characters.')
      .max(128, 'Use at most 128 characters.'),
    confirmPassword: z.string(),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'The passwords do not match.',
  });

type PasswordValues = z.infer<typeof passwordSchema>;

function PasswordCard() {
  const { dataSource } = useServices();
  const changePassword = useChangePassword();
  const { register, handleSubmit, formState, reset } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { currentPassword: '', newPassword: '', confirmPassword: '' },
  });

  const onSubmit = handleSubmit((values) =>
    changePassword.mutate(
      { currentPassword: values.currentPassword, newPassword: values.newPassword },
      {
        onSuccess: () => {
          reset();
          toast.success(
            'Password changed',
            dataSource === 'demo'
              ? 'Demo mode: nothing was actually changed.'
              : 'Use the new password the next time you sign in.',
          );
        },
        onError: (error) => toast.danger('Password not changed', error.message),
      },
    ),
  );

  return (
    <Card>
      <CardHeader
        title="Password"
        description="Passwords are hashed with scrypt by the backend and never stored in the browser."
      />
      <CardBody>
        <form noValidate onSubmit={onSubmit} aria-label="Change password" className="space-y-5">
          <Field label="Current password" required error={formState.errors.currentPassword?.message}>
            {(control) => (
              <Input
                {...control}
                {...register('currentPassword')}
                type="password"
                autoComplete="current-password"
              />
            )}
          </Field>
          <Field
            label="New password"
            required
            hint="At least 12 characters. Length matters more than symbols."
            error={formState.errors.newPassword?.message}
          >
            {(control) => (
              <Input
                {...control}
                {...register('newPassword')}
                type="password"
                autoComplete="new-password"
              />
            )}
          </Field>
          <Field label="Repeat new password" required error={formState.errors.confirmPassword?.message}>
            {(control) => (
              <Input
                {...control}
                {...register('confirmPassword')}
                type="password"
                autoComplete="new-password"
              />
            )}
          </Field>
          <div className="flex justify-end">
            <Button type="submit" loading={changePassword.isPending}>
              Change password
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

export function SecuritySettings() {
  const session = useCurrentSession();
  const { dataSource } = useServices();

  return (
    <div className="space-y-6">
      {dataSource === 'demo' && (
        <Alert tone="warning" title="Demo mode: nothing here is authenticated">
          These controls talk to in-memory demo services. Switch the data source to the backend API
          in Settings → API to use real accounts, sessions and roles.
        </Alert>
      )}

      <PasswordCard />

      <Card>
        <CardHeader title="Multi-factor authentication" />
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <KeyRound aria-hidden="true" className="size-5 text-fg-subtle" />
            <div>
              <p className="text-sm font-medium text-fg">Authenticator app or passkey</p>
              <p className="text-xs text-fg-muted">
                Not implemented. Password sign-in is the only method today.
              </p>
            </div>
          </div>
          <Button variant="secondary" disabled>
            Set up MFA
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="This session"
          description="Sessions are held server-side and can be revoked by signing out."
        />
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Monitor aria-hidden="true" className="size-5 text-fg-subtle" />
            <div>
              <p className="text-sm font-medium text-fg">This browser</p>
              <p className="text-xs text-fg-muted">
                {session
                  ? `Expires ${formatDateTime(session.expiresAt)}. Signed in as ${session.user.email}.`
                  : 'No active session.'}
              </p>
            </div>
          </div>
          <Badge tone={dataSource === 'demo' ? 'info' : 'success'}>
            {dataSource === 'demo' ? 'Demo' : 'Active'}
          </Badge>
        </CardBody>
      </Card>
    </div>
  );
}
