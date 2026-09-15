import { TriangleAlert } from 'lucide-react';
import { isRouteErrorResponse, useRouteError } from 'react-router';
import { Button, LinkButton } from '@/components/ui/Button';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import NotFoundPage from './NotFoundPage';

/**
 * Route-level error boundary. Shows a friendly message and recovery options;
 * never renders error messages or stack traces from the thrown value.
 */
export default function RouteErrorPage() {
  const error = useRouteError();
  useDocumentTitle('Something went wrong');

  if (isRouteErrorResponse(error) && error.status === 404) {
    return <NotFoundPage />;
  }

  return (
    <div role="alert" className="mx-auto flex max-w-lg flex-col items-center px-4 py-16 text-center">
      <span className="mb-4 rounded-xl border border-danger/25 bg-danger-soft p-3 text-danger">
        <TriangleAlert aria-hidden="true" className="size-6" />
      </span>
      <h1 className="text-2xl font-semibold text-fg">Something went wrong</h1>
      <p className="mt-2 text-sm text-fg-muted">
        This page failed to load. You can try again, or return to the dashboard.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button variant="primary" onClick={() => window.location.reload()}>
          Reload page
        </Button>
        <LinkButton to="/dashboard" variant="secondary">
          Go to dashboard
        </LinkButton>
      </div>
    </div>
  );
}
