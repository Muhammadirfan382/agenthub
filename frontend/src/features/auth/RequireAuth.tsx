import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { LoadingState } from '@/components/feedback/LoadingState';
import { useSession } from './api';

/**
 * Sends anyone without a session to the sign-in page.
 *
 * This is navigation, not protection: the data behind these routes is
 * protected by the API, which refuses every request without a valid session.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: session, isPending, isError, error } = useSession();
  const location = useLocation();

  if (isPending) {
    return (
      <div className="grid min-h-dvh place-items-center bg-canvas">
        <LoadingState variant="inline" label="Checking your session…" />
      </div>
    );
  }

  if (isError) {
    // The API could not be reached at all; say so instead of pretending the
    // user is signed out, which would hide the real problem.
    return (
      <div className="grid min-h-dvh place-items-center bg-canvas px-4">
        <div className="max-w-md text-center">
          <h1 className="text-lg font-semibold text-fg">AgentHub cannot reach the backend</h1>
          <p className="mt-2 text-sm text-fg-muted">
            {error instanceof Error ? error.message : 'The API did not respond.'}
          </p>
          <p className="mt-2 text-sm text-fg-muted">
            Start the API, or switch back to demo mode in Settings.
          </p>
        </div>
      </div>
    );
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  }

  return <>{children}</>;
}
