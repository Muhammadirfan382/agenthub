import type { LiveResource } from './contracts';
import { useServices } from './ServicesContext';

/** True when the backend really serves this resource in the current data source. */
export function useIsLive(resource: LiveResource): boolean {
  return useServices().liveResources.includes(resource);
}
