import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { appConfig } from '@/config/env';
import type { DataSource } from '@/services/contracts';

interface DataSourceState {
  dataSource: DataSource;
  setDataSource: (dataSource: DataSource) => void;
}

/**
 * Which service implementation the app uses. Persisted so a reload keeps the
 * choice; it holds a single non-sensitive enum and is not a security control.
 */
export const useDataSourceStore = create<DataSourceState>()(
  persist(
    (set) => ({
      dataSource: appConfig.dataSource,
      setDataSource: (dataSource) => set({ dataSource }),
    }),
    { name: 'agenthub-data-source', storage: createJSONStorage(() => localStorage) },
  ),
);
