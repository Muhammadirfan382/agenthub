import { BadgeCheck, Star, Users } from 'lucide-react';
import { Link } from 'react-router';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { Badge } from '@/components/ui/Badge';
import { Meter, type MeterTone } from '@/components/ui/Meter';
import { formatCompact, formatRelative } from '@/lib/format';
import type { MarketplaceListing } from '@/types/domain';

function ratingTone(rating: number): MeterTone {
  if (rating >= 80) return 'success';
  if (rating >= 60) return 'warning';
  return 'danger';
}

export function MarketplaceCard({ listing }: { listing: MarketplaceListing }) {
  return (
    <article className="relative flex h-full flex-col rounded-lg border border-line bg-surface p-4 shadow-card transition-colors hover:border-line-strong">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-fg">
            <Link to={`/agents/${listing.agentId}`} className="after:absolute after:inset-0 hover:underline focus-visible:outline-2 focus-visible:outline-ring">
              {listing.name}
            </Link>
          </h2>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-fg-muted">
            {listing.publisher}
            {listing.verified && (
              <span className="inline-flex items-center gap-0.5 text-success">
                <BadgeCheck aria-hidden="true" className="size-3.5" />
                Verified
              </span>
            )}
          </p>
        </div>
        <Badge>{CATEGORY_LABELS[listing.category]}</Badge>
      </div>

      <p className="mt-3 flex-1 text-sm text-fg-muted">{listing.summary}</p>

      <ul aria-label="Tags" className="mt-3 flex flex-wrap gap-1.5">
        {listing.tags.slice(0, 3).map((tag) => (
          <li key={tag}>
            <Badge tone="brand">{tag}</Badge>
          </li>
        ))}
      </ul>

      <div className="mt-4 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-fg-muted">Security rating (demo)</span>
          <span className="font-medium text-fg tabular-nums">{listing.securityRating}/100</span>
        </div>
        <Meter value={listing.securityRating} label={`Demo security rating for ${listing.name}`} valueText={`${listing.securityRating} out of 100`} tone={ratingTone(listing.securityRating)} />
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-xs text-fg-muted">
        <span className="inline-flex items-center gap-1 tabular-nums">
          <Star aria-hidden="true" className="size-3.5 fill-warning text-warning" />
          {listing.rating.toFixed(1)}
          <span className="text-fg-subtle">({listing.ratingCount} demo ratings)</span>
        </span>
        <span className="inline-flex items-center gap-1 tabular-nums">
          <Users aria-hidden="true" className="size-3.5" />
          {formatCompact(listing.demoUsageCount)} demo uses
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <RiskBadge level={listing.riskLevel} />
        <span className="text-xs text-fg-subtle">Added {formatRelative(listing.publishedAt)}</span>
      </div>
    </article>
  );
}
