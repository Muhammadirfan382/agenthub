import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/services/http/client';
import { queryKeys } from '@/services/queryKeys';

export interface QueryClientOptions {
  retry?: number;
  /** Extra handling after the session has been dropped (used by tests). */
  onUnauthenticated?: () => void;
}

function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function createQueryClient(options: QueryClientOptions = {}): QueryClient {
  const holder: { client?: QueryClient } = {};

  // One rule for the whole app: if any request says the session is gone, the
  // session is gone. The route guard then sends the user to sign in.
  const handleError = (error: unknown) => {
    if (!isUnauthenticated(error)) return;
    holder.client?.setQueryData(queryKeys.auth.session, null);
    options.onUnauthenticated?.();
  };

  holder.client = new QueryClient({
    queryCache: new QueryCache({ onError: handleError }),
    mutationCache: new MutationCache({ onError: handleError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Retrying a refused request cannot make it succeed.
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
          return failureCount < (options.retry ?? 1);
        },
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
  return holder.client;
}
