import { SearchX } from 'lucide-react';
import { LinkButton } from '@/components/ui/Button';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export default function NotFoundPage() {
  useDocumentTitle('Page not found');
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-16 text-center">
      <span className="mb-4 rounded-xl border border-line bg-surface p-3 text-fg-subtle shadow-card">
        <SearchX aria-hidden="true" className="size-6" />
      </span>
      <p className="font-mono text-sm text-fg-subtle">404</p>
      <h1 className="mt-1 text-2xl font-semibold text-fg">Page not found</h1>
      <p className="mt-2 text-sm text-fg-muted">The page you requested does not exist or has moved.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <LinkButton to="/dashboard" variant="primary">
          Go to dashboard
        </LinkButton>
        <LinkButton to="/agents" variant="secondary">
          Browse agents
        </LinkButton>
      </div>
    </div>
  );
}
