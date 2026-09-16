import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Navigate, useLocation, useNavigate } from 'react-router';
import { z } from 'zod';
import { LoadingState } from '@/components/feedback/LoadingState';
import { LogoMark } from '@/components/layout/Logo';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useServices } from '@/services/ServicesContext';
import { useLogin, useSession } from './api';

const loginSchema = z.object({
  email: z.email('Enter your email address.').max(254),
  password: z.string().min(1, 'Enter your password.').max(256),
});

type LoginValues = z.infer<typeof loginSchema>;

/** Only a path inside this app is an acceptable redirect target. */
function safeRedirect(target: unknown): string {
  return typeof target === 'string' && target.startsWith('/') && !target.startsWith('//')
    ? target
    : '/dashboard';
}

export default function LoginPage() {
  useDocumentTitle('Sign in');
  const { dataSource } = useServices();
  const session = useSession();
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const destination = safeRedirect((location.state as { from?: unknown } | null)?.from);

  const { register, handleSubmit, formState } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  if (session.isPending) {
    return (
      <div className="grid min-h-dvh place-items-center bg-canvas">
        <LoadingState variant="inline" label="Checking your session…" />
      </div>
    );
  }
  if (session.data) {
    return <Navigate to={destination} replace />;
  }

  const onSubmit = handleSubmit((values) =>
    login.mutate(values, { onSuccess: () => navigate(destination, { replace: true }) }),
  );

  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <LogoMark className="size-8" />
          <span className="text-lg font-semibold text-fg">AgentHub</span>
        </div>

        <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
          <h1 className="text-base font-semibold text-fg">Sign in</h1>
          <p className="mt-1 text-sm text-fg-muted">
            {dataSource === 'demo'
              ? 'Demo mode: nothing is authenticated and any password is accepted.'
              : 'Use the account an administrator created for you.'}
          </p>

          <form noValidate onSubmit={onSubmit} aria-label="Sign in" className="mt-5 space-y-4">
            <Field label="Email" required error={formState.errors.email?.message}>
              {(control) => (
                <Input
                  {...control}
                  {...register('email')}
                  type="email"
                  autoComplete="username"
                  autoFocus
                  placeholder="you@example.com"
                />
              )}
            </Field>
            <Field label="Password" required error={formState.errors.password?.message}>
              {(control) => (
                <Input
                  {...control}
                  {...register('password')}
                  type="password"
                  autoComplete="current-password"
                />
              )}
            </Field>

            <div aria-live="polite">
              {login.isError && (
                <Alert tone="danger" title="Could not sign in">
                  {login.error instanceof Error
                    ? login.error.message
                    : 'Check your details and try again.'}
                </Alert>
              )}
            </div>

            <Button type="submit" variant="primary" className="w-full" loading={login.isPending}>
              Sign in
            </Button>
          </form>

          <p className="mt-5 border-t border-line pt-4 text-xs text-fg-muted">
            AgentHub has no public sign-up. Accounts are created by an administrator with the
            <code className="mx-1 font-mono">create_user</code>
            script, then added to an organization.
          </p>
        </div>
      </div>
    </main>
  );
}
