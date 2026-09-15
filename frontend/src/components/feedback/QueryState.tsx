import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ErrorState } from './ErrorState';
import { LoadingState } from './LoadingState';

interface QueryStateProps<T> {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
  loading?: ReactNode;
  errorTitle?: string;
  errorMessage?: string;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
}

/**
 * Renders the loading, error, empty and success states of a query consistently.
 * A failed request is never shown as an empty list.
 */
export function QueryState<T>({ query, children, loading, errorTitle, errorMessage, isEmpty, empty }: QueryStateProps<T>) {
  if (query.isPending) return <>{loading ?? <LoadingState />}</>;
  if (query.isError) {
    return (
      <ErrorState
        title={errorTitle}
        message={errorMessage}
        onRetry={() => void query.refetch()}
        retrying={query.isFetching}
      />
    );
  }
  if (isEmpty?.(query.data) && empty) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
