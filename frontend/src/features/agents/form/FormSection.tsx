import type { ReactNode } from 'react';
import { Card } from '@/components/ui/Card';

interface FormSectionProps {
  id: string;
  step: number;
  title: string;
  description?: string;
  children: ReactNode;
}

/** A numbered form section rendered as a fieldset with a visible legend. */
export function FormSection({ id, step, title, description, children }: FormSectionProps) {
  return (
    <Card id={id} className="scroll-mt-20">
      <fieldset className="min-w-0">
        <legend className="sr-only">{`${step}. ${title}`}</legend>
        <div aria-hidden="true" className="flex items-start gap-3 border-b border-line px-5 py-4">
          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand-strong">{step}</span>
          <div>
            <p className="text-sm font-semibold text-fg">{title}</p>
            {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
          </div>
        </div>
        <div className="space-y-5 px-5 py-5">{children}</div>
      </fieldset>
    </Card>
  );
}
