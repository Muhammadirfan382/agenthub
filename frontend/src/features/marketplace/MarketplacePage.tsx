import { SearchX, Store } from 'lucide-react';
import { useId } from 'react';
import { useSearchParams } from 'react-router';
import { DataNotice } from '@/components/feedback/DemoNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { PageHeader } from '@/components/layout/PageHeader';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { Button } from '@/components/ui/Button';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import type { MarketplaceCollection, MarketplaceParams } from '@/services/contracts';
import { AGENT_CATEGORIES } from '@/types/domain';
import { useMarketplace, useMarketplaceTags } from './api';
import { MarketplaceCard } from './components/MarketplaceCard';

const COLLECTIONS: { id: MarketplaceCollection; label: string }[] = [
  { id: 'all', label: 'All agents' },
  { id: 'verified', label: 'Verified' },
  { id: 'installed', label: 'Installed' },
];

export default function MarketplacePage() {
  const idPrefix = useId();
  const [searchParams, setSearchParams] = useSearchParams();
  const collectionParam = searchParams.get('collection');
  const params: Required<MarketplaceParams> = {
    search: searchParams.get('q') ?? '',
    category: (searchParams.get('category') as MarketplaceParams['category']) ?? 'all',
    tag: searchParams.get('tag') ?? '',
    collection: COLLECTIONS.some((c) => c.id === collectionParam) ? (collectionParam as MarketplaceCollection) : 'all',
  };
  const query = useMarketplace(params);
  const tags = useMarketplaceTags();

  const update = (patch: Partial<MarketplaceParams>) => {
    const next = { ...params, ...patch };
    const out = new URLSearchParams();
    if (next.search) out.set('q', next.search);
    if (next.category !== 'all') out.set('category', next.category);
    if (next.tag) out.set('tag', next.tag);
    if (next.collection !== 'all') out.set('collection', next.collection);
    setSearchParams(out, { replace: true });
  };

  const filtered = Boolean(params.search || params.category !== 'all' || params.tag);

  return (
    <>
      <PageHeader
        title="Marketplace"
        description="Discover agents by what they do, how they are verified and how much access they ask for."
      />

      <DataNotice
        resource="marketplace"
        className="mb-6"
        demoTitle="Demo marketplace data"
        demo="Ratings, usage counts and security ratings are invented for demonstration. They are not real downloads, users, reviews, execution statistics or security scan results."
        live="Every listing is a published version of a real agent. Installing one grants it only what you choose: nothing is granted by installing."
      />

      <Tabs label="Collections" idPrefix={idPrefix} items={COLLECTIONS} value={params.collection} onChange={(collection) => update({ collection })} />

      <TabPanel idPrefix={idPrefix} id={params.collection} className="pt-4">
        <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
          <SearchInput label="Search the marketplace" placeholder="Search agents, tags or publishers" value={params.search} onChange={(e) => update({ search: e.target.value })} />
          <Select aria-label="Filter by category" value={params.category} onChange={(e) => update({ category: e.target.value as MarketplaceParams['category'] })}>
            <option value="all">All categories</option>
            {AGENT_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {CATEGORY_LABELS[category]}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by tag" value={params.tag} onChange={(e) => update({ tag: e.target.value })} disabled={!tags.data}>
            <option value="">All tags</option>
            {(tags.data ?? []).map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </Select>
        </div>

        <QueryState
          query={query}
          loading={<LoadingState variant="cards" label="Loading marketplace…" />}
          errorTitle="The marketplace could not be loaded"
          isEmpty={(listings) => listings.length === 0}
          empty={
            filtered ? (
              <EmptyState
                icon={SearchX}
                title="No agents match these filters"
                action={
                  <Button variant="secondary" size="sm" onClick={() => update({ search: '', category: 'all', tag: '' })}>
                    Clear filters
                  </Button>
                }
              />
            ) : (
              <EmptyState icon={Store} title="No agents in this collection" />
            )
          }
        >
          {(listings) => (
            <>
              <p aria-live="polite" className="mb-3 text-sm text-fg-muted">
                {listings.length} {listings.length === 1 ? 'agent' : 'agents'}
              </p>
              <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {listings.map((listing) => (
                  <li key={listing.id}>
                    <MarketplaceCard listing={listing} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </QueryState>
      </TabPanel>
    </>
  );
}
