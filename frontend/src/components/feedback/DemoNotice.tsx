import { FlaskConical } from 'lucide-react';
import type { ReactNode } from 'react';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';

/** Small inline label marking a section as demonstration data. */
export function DemoBadge({ label = 'Demo data' }: { label?: string }) {
  return (
    <Badge tone="info" icon={<FlaskConical aria-hidden="true" className="size-3" />}>
      {label}
    </Badge>
  );
}

interface DemoNoticeProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

/** Page-level statement of what is simulated and what is not implemented yet. */
export function DemoNotice({ title = 'Demonstration data', children, className }: DemoNoticeProps) {
  return (
    <Alert tone="info" title={title} className={className}>
      {children}
    </Alert>
  );
}
