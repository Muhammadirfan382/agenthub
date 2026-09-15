import { ChevronRight } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export interface Breadcrumb {
  label: string;
  to?: string;
}

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumbs?: Breadcrumb[];
  meta?: ReactNode;
  /** Overrides the browser tab title when it should differ from the heading. */
  documentTitle?: string;
}

export function PageHeader({ title, description, actions, breadcrumbs, meta, documentTitle }: PageHeaderProps) {
  useDocumentTitle(documentTitle ?? title);

  return (
    <div className="mb-6 space-y-3">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb">
          <ol className="flex flex-wrap items-center gap-1 text-xs text-fg-subtle">
            {breadcrumbs.map((crumb, index) => (
              <li key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                {index > 0 && <ChevronRight aria-hidden="true" className="size-3" />}
                {crumb.to ? (
                  <Link to={crumb.to} className="rounded hover:text-fg focus-visible:outline-2 focus-visible:outline-ring">
                    {crumb.label}
                  </Link>
                ) : (
                  <span aria-current="page" className="text-fg-muted">
                    {crumb.label}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-fg">{title}</h1>
          {description && <p className="mt-1 max-w-3xl text-sm text-fg-muted">{description}</p>}
          {meta && <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
