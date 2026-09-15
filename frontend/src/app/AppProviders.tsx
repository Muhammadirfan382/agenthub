import { type QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { Services } from '@/services/contracts';
import { ServicesProvider } from '@/services/ServicesProvider';

interface AppProvidersProps {
  services: Services;
  queryClient: QueryClient;
  children: ReactNode;
}

/** Shared by the app and the test harness so both use identical wiring. */
export function AppProviders({ services, queryClient, children }: AppProvidersProps) {
  return (
    <ServicesProvider services={services}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ServicesProvider>
  );
}
