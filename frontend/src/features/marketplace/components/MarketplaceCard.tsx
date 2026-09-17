import { BadgeCheck, CheckCircle2, Star, Users, Wrench } from 'lucide-react';
import { Link } from 'react-router';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS } from '@/components/status/meta';
import { Badge } from '@/components/ui/Badge';
import { formatCompact, formatRelative } from '@/lib/format';
import type { MarketplaceListing } from '@/types/domain';

export function MarketplaceCard({ listing }: { listing: MarketplaceListing }) {
  const stats = listing.demoStats;

  return (
    <article className="relative flex h-full flex-col rounded-lg border border-line bg-surface p-4 shadow-card transition-colors hover:border-line-strong">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-fg">
            <Link
              to={`/marketplace/${listing.id}`}
              className="after:absolute after:inset-0 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              {listing.name}
            </Link>
          </h2>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-fg-muted">
            {listing.publisher}
            {listing.verification === 'verified' && (
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

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-fg-muted">
        <span className="font-mono text-fg">v{listing.version}</span>
        <span className="inline-flex items-center gap-1">
          <Wrench aria-hidden="true" className="size-3.5" />
          {listing.tools.length} {listing.tools.length === 1 ? 'tool' : 'tools'}
        </span>
        {listing.own && <Badge tone="neutral">Yours</Badge>}
        {listing.installed && (
          <Badge tone="success" icon={<CheckCircle2 aria-hidden="true" className="size-3" />}>
            Installed
          </Badge>
        )}
      </div>

      {/* Invented numbers exist only in demo mode, and say so. */}
      {stats && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-xs text-fg-muted">
          <span className="inline-flex items-center gap-1 tabular-nums">
            <Star aria-hidden="true" className="size-3.5 fill-warning text-warning" />
            {stats.rating.toFixed(1)}
            <span className="text-fg-subtle">({stats.ratingCount} demo ratings)</span>
          </span>
          <span className="inline-flex items-center gap-1 tabular-nums">
            <Users aria-hidden="true" className="size-3.5" />
            {formatCompact(stats.usageCount)} demo uses
          </span>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3">
        <RiskBadge level={listing.riskLevel} />
        <span className="text-xs text-fg-subtle">Published {formatRelative(listing.publishedAt)}</span>
      </div>
    </article>
  );
}
