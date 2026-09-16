import { FlaskConical, Server } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { useServices } from '@/services/ServicesContext';

/** States plainly whether the screen is showing demo data or real backend data. */
export function DataSourceBadge() {
  const { dataSource } = useServices();

  if (dataSource === 'demo') {
    return (
      <Badge tone="info" icon={<FlaskConical aria-hidden="true" className="size-3" />} title="Everything on screen is demonstration data.">
        Demo mode
      </Badge>
    );
  }

  return (
    <Badge tone="success" icon={<Server aria-hidden="true" className="size-3" />} title="Agents, executions and dashboard counts come from the backend. Other sections are still demo data.">
      API mode
    </Badge>
  );
}
