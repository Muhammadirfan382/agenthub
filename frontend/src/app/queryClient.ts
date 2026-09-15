import { QueryClient } from '@tanstack/react-query';

export function createQueryClient(options: { retry?: number } = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: options.retry ?? 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
