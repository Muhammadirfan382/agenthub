import { FlaskConical } from 'lucide-react';
import type { ReactNode } from 'react';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import type { LiveResource } from '@/services/contracts';
import { useIsLive } from '@/services/useIsLive';

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

interface DataNoticeProps {
  resource: LiveResource;
  demo: ReactNode;
  live: ReactNode;
  demoTitle?: string;
  liveTitle?: string;
  className?: string;
}

/**
 * Says where the data on the page actually comes from. Keeping both messages
 * together makes it hard to leave a stale "demonstration data" claim on a page
 * that is reading from the backend.
 */
export function DataNotice({ resource, demo, live, demoTitle, liveTitle = 'Live backend data', className }: DataNoticeProps) {
  if (!useIsLive(resource)) {
    return (
      <DemoNotice title={demoTitle} className={className}>
        {demo}
      </DemoNotice>
    );
  }
  return (
    <Alert tone="info" title={liveTitle} className={className}>
      {live}
    </Alert>
  );
}
