import { BadgeCheck, Download, SearchX, Trash2, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { LoadingState } from '@/components/feedback/LoadingState';
import { PageHeader } from '@/components/layout/PageHeader';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CAPABILITY_META, CATEGORY_LABELS, PERMISSION_LEVEL_META } from '@/components/status/meta';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { usePermission } from '@/features/auth/api';
import { formatDateTime } from '@/lib/format';
import { deriveRisk } from '@/lib/risk';
import { toast } from '@/stores/toastStore';
import type { MarketplaceListingDetail } from '@/types/domain';
import { useInstall, useInstallation, useListing, useUninstall } from './api';
import { GrantEditor } from './components/GrantEditor';
import { emptyGrants, type GrantState, grantsFrom, toGrantList } from './grants';

export default function MarketplaceListingPage() {
  const { id = '' } = useParams();
  const query = useListing(id);

  if (query.isPending) return <LoadingState label="Loading listing…" />;
  if (query.isError) {
    return (
      <ErrorState
        title="Listing could not be loaded"
        onRetry={() => void query.refetch()}
        retrying={query.isFetching}
      />
    );
  }
  if (!query.data) {
    return (
      <EmptyState
        icon={SearchX}
        title="Listing not found"
        description="It may have been unpublished, or it is not shared with your organization."
        action={
          <LinkButton to="/marketplace" variant="primary" size="sm">
            Back to the marketplace
          </LinkButton>
        }
      />
    );
  }
  return <Listing listing={query.data} />;
}

function Listing({ listing }: { listing: MarketplaceListingDetail }) {
  const permitted = usePermission();
  const canInstall = permitted('installation:manage');
  const install = useInstall();
  const uninstall = useUninstall();
  const installation = useInstallation(listing.installationId ?? '');
  const [grants, setGrants] = useState<GrantState>(emptyGrants());
  const [note, setNote] = useState('');
  const [confirmUninstall, setConfirmUninstall] = useState(false);

  const requested = listing.manifest.requiredPermissions.filter((p) => p.level !== 'denied');
  const chosen = toGrantList(grants);
  const projected = deriveRisk(chosen);
  const current = listing.installed && installation.data ? installation.data : null;

  const submit = () =>
    install.mutate(
      { agentVersionId: listing.id, grants: chosen, note: note.trim() || null },
      {
        onSuccess: (created) => {
          setGrants(grantsFrom(created.grants));
          toast.success(
            `${listing.name} installed`,
            created.unusableTools.length
              ? `Granted ${chosen.length} of ${requested.length} requested capabilities. Some tools cannot run.`
              : `Granted ${chosen.length} of ${requested.length} requested capabilities.`,
          );
        },
        onError: (error) => toast.danger('Could not install', error.message),
      },
    );

  return (
    <>
      <PageHeader
        title={listing.name}
        documentTitle={`${listing.name} · Marketplace`}
        description={listing.summary}
        breadcrumbs={[{ label: 'Marketplace', to: '/marketplace' }, { label: listing.name }]}
        meta={
          <>
            <Badge>{CATEGORY_LABELS[listing.category]}</Badge>
            <Badge>v{listing.version}</Badge>
            <RiskBadge level={listing.riskLevel} />
            {listing.verification === 'verified' && (
              <Badge tone="success" icon={<BadgeCheck aria-hidden="true" className="size-3" />}>
                Verified
              </Badge>
            )}
            {listing.installed && <Badge tone="success">Installed</Badge>}
          </>
        }
        actions={
          listing.installed && listing.installationId ? (
            <Button
              variant="secondary"
              onClick={() => setConfirmUninstall(true)}
              disabled={!canInstall}
            >
              <Trash2 aria-hidden="true" className="size-4" />
              Uninstall
            </Button>
          ) : null
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          <Card>
            <CardHeader
              title="What this agent asks for"
              description="A published manifest is frozen: this is exactly what version was reviewed."
            />
            <CardBody className="space-y-4">
              {requested.length === 0 ? (
                <p className="text-sm text-fg-muted">
                  Nothing. It asks for no capabilities at all.
                </p>
              ) : (
                <ul className="space-y-3">
                  {requested.map((permission) => {
                    const meta = CAPABILITY_META[permission.capability];
                    return (
                      <li
                        key={permission.capability}
                        className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line p-3"
                      >
                        <div className="min-w-0">
                          <p className="flex items-center gap-2 text-sm font-medium text-fg">
                            <meta.icon aria-hidden="true" className="size-4 text-fg-subtle" />
                            {meta.label}
                          </p>
                          <p className="mt-0.5 text-xs text-fg-muted">{permission.scope}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          {permission.requiresApproval && <Badge tone="warning">Approval required</Badge>}
                          <Badge>{PERMISSION_LEVEL_META[permission.level].label}</Badge>
                          <RiskBadge level={permission.risk} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-fg-subtle">Tools</dt>
                  <dd className="mt-0.5 text-fg">
                    {listing.tools.length ? listing.tools.join(', ') : 'None'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-fg-subtle">Model</dt>
                  <dd className="mt-0.5 text-fg">{listing.manifest.model.model}</dd>
                </div>
                <div>
                  <dt className="text-xs text-fg-subtle">Sandbox</dt>
                  <dd className="mt-0.5 text-fg">{listing.manifest.securityPolicy.sandbox}</dd>
                </div>
                <div>
                  <dt className="text-xs text-fg-subtle">Network egress</dt>
                  <dd className="mt-0.5 text-fg">
                    {listing.manifest.securityPolicy.networkEgress === 'none'
                      ? 'None'
                      : listing.manifest.securityPolicy.allowedDomains.join(', ') || 'Allow-list'}
                  </dd>
                </div>
              </dl>
            </CardBody>
          </Card>

          {current ? (
            <Card>
              <CardHeader
                title="What you granted"
                description="Installed agents only ever get what is listed here."
              />
              <CardBody className="space-y-3">
                {current.unusableTools.length > 0 && (
                  <Alert tone="warning" title="Some tools cannot run">
                    {current.unusableTools.join(', ')} need capabilities you did not grant.
                  </Alert>
                )}
                <ul className="space-y-2">
                  {current.grants
                    .filter((grant) => grant.level !== 'denied')
                    .map((grant) => (
                      <li key={grant.capability} className="flex items-center justify-between gap-2 text-sm">
                        <span className="text-fg">{CAPABILITY_META[grant.capability].label}</span>
                        <span className="flex items-center gap-2">
                          <span className="text-xs text-fg-muted">{grant.scope}</span>
                          <Badge>{PERMISSION_LEVEL_META[grant.level].label}</Badge>
                        </span>
                      </li>
                    ))}
                  {current.grants.every((grant) => grant.level === 'denied') && (
                    <li className="text-sm text-fg-muted">Nothing was granted.</li>
                  )}
                </ul>
                <p className="text-xs text-fg-subtle">
                  Installed {formatDateTime(current.createdAt)} by {current.installedBy}.
                </p>
              </CardBody>
            </Card>
          ) : (
            <Card>
              <CardHeader
                title="Grant what you are comfortable with"
                description="Everything starts denied. Anything you do not grant stays denied."
              />
              <CardBody className="space-y-4">
                {!canInstall && (
                  <Alert tone="info" title="Your role cannot install agents">
                    Ask an administrator or the owner of your organization.
                  </Alert>
                )}
                <GrantEditor
                  requested={listing.manifest.requiredPermissions}
                  value={grants}
                  onChange={setGrants}
                  disabled={!canInstall || listing.own}
                />
                <Field label="Note (optional)" hint="Why this level of access was agreed.">
                  {(control) => (
                    <Input
                      {...control}
                      value={note}
                      disabled={!canInstall || listing.own}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Trial install for the research team"
                    />
                  )}
                </Field>
              </CardBody>
            </Card>
          )}
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader title="Publisher" />
            <CardBody className="space-y-2 text-sm">
              <p className="font-medium text-fg">{listing.publisher}</p>
              <p className="text-xs text-fg-muted">
                Published {formatDateTime(listing.publishedAt)}
              </p>
              {listing.own && (
                <Alert tone="info" title="This is your organization's agent">
                  It does not need installing; open it from the Agents page.
                </Alert>
              )}
            </CardBody>
          </Card>

          {!listing.installed && !listing.own && (
            <Card>
              <CardHeader title="Install" />
              <CardBody className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-fg-muted">Granting</span>
                  <span className="font-medium text-fg tabular-nums">
                    {chosen.length} of {requested.length}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-fg-muted">Resulting risk</span>
                  <RiskBadge level={projected.level} />
                </div>
                {chosen.length === 0 && requested.length > 0 && (
                  <p className="flex items-start gap-2 text-xs text-fg-muted">
                    <TriangleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                    You can install with nothing granted; tools that need those capabilities will
                    not work.
                  </p>
                )}
                <Button
                  variant="primary"
                  className="w-full"
                  loading={install.isPending}
                  disabled={!canInstall}
                  onClick={submit}
                >
                  <Download aria-hidden="true" className="size-4" />
                  Install agent
                </Button>
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader title="Changelog" />
            <CardBody>
              <ul className="list-disc space-y-1 pl-4 text-sm text-fg-muted">
                {listing.changelog.map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmUninstall}
        tone="danger"
        title={`Uninstall ${listing.name}?`}
        description="The grants you made are removed. The agent stays in the marketplace and can be installed again."
        confirmLabel="Uninstall"
        pending={uninstall.isPending}
        onCancel={() => setConfirmUninstall(false)}
        onConfirm={() => {
          if (!listing.installationId) return;
          uninstall.mutate(listing.installationId, {
            onSuccess: () => {
              setConfirmUninstall(false);
              setGrants(emptyGrants());
              toast.success(`${listing.name} uninstalled`);
            },
            onError: (error) => {
              setConfirmUninstall(false);
              toast.danger('Could not uninstall', error.message);
            },
          });
        }}
      />
    </>
  );
}
