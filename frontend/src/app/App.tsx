import { useMemo, useState } from 'react';
import { createBrowserRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { createServices } from '@/services';
import { useDataSourceStore } from '@/stores/dataSourceStore';
import { AppProviders } from './AppProviders';
import { createQueryClient } from './queryClient';
import { routes } from './routes';

export function App() {
  const dataSource = useDataSourceStore((state) => state.dataSource);
  const [router] = useState(() => createBrowserRouter(routes));

  // Switching the data source rebuilds the services and starts from an empty
  // cache, so demo rows can never be shown as if they came from the backend.
  const { services, queryClient } = useMemo(
    () => ({ services: createServices(dataSource), queryClient: createQueryClient() }),
    [dataSource],
  );

  return (
    <AppProviders services={services} queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
