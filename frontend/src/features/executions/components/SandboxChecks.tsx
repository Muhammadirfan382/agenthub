import { CircleCheck, CircleX } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import type { SandboxReport } from '@/types/domain';

/**
 * What a container reported about its own isolation, one guarantee per row.
 * A failed row names the promise that was not kept and why.
 */
export function SandboxChecks({ report }: { report: SandboxReport }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-fg">{report.summary}</p>
        <Badge tone={report.passed ? 'success' : 'danger'}>
          {report.passed ? 'Isolated' : 'Not isolated'}
        </Badge>
      </div>
      <ul className="divide-y divide-border rounded-md border border-border" aria-label="Isolation checks">
        {report.checks.map((check) => (
          <li key={check.id} className="flex items-start gap-3 px-3 py-2">
            {check.passed ? (
              <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
            ) : (
              <CircleX aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-danger" />
            )}
            <div className="min-w-0">
              <p className="text-sm text-fg">
                {check.label}
                <span className="sr-only">{check.passed ? ': kept' : ': broken'}</span>
              </p>
              <p className="text-xs break-words text-fg-muted">{check.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
