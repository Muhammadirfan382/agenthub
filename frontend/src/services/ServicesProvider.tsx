import type { ReactNode } from 'react';
import type { Services } from './contracts';
import { ServicesContext } from './ServicesContext';

export function ServicesProvider({ services, children }: { services: Services; children: ReactNode }) {
  return <ServicesContext value={services}>{children}</ServicesContext>;
}
