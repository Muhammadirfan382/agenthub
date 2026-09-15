import { useState } from 'react';
import { createBrowserRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { createServices } from '@/services';
import { AppProviders } from './AppProviders';
import { createQueryClient } from './queryClient';
import { routes } from './routes';

export function App() {
  const [services] = useState(createServices);
  const [queryClient] = useState(() => createQueryClient());
  const [router] = useState(() => createBrowserRouter(routes));

  return (
    <AppProviders services={services} queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
