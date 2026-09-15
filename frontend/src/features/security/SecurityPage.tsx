import { ShieldAlert, ShieldCheck, ShieldX, TriangleAlert } from 'lucide-react';
import { DemoBadge, DemoNotice } from '@/components/feedback/DemoNotice';
import { LoadingState } from '@/components/feedback/LoadingState';
import { QueryState } from '@/components/feedback/QueryState';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/ui/Card';
import { StatCard } from '@/components/ui/StatCard';
import { usePolicies, useSecurityEvents, useSecurityOverview } from './api';
import { RiskDistributionCard, SecurityChecksCard } from './components/SecurityOverviewCards';
import { AlertsList, PermissionOverviewTable, PolicyList, SecurityEventsTable } from './components/SecurityTables';

export default function SecurityPage() {
  const overview = useSecurityOverview();
  const events = useSecurityEvents();
  const policies = usePolicies();

  return (
    <>
      <PageHeader title="Security" description="Agent risk, permissions, security checks, events and policy status." meta={<DemoBadge label="Demo security data" />} />

      <DemoNotice title="Demo security data" className="mb-6">
        No security scanning, threat detection or policy enforcement exists yet. Everything on this page is demonstration
        data that shows how real security analysis will be presented once the security layer is built.
      </DemoNotice>

      <QueryState query={overview} loading={<LoadingState label="Loading security overview…" />} errorTitle="Security overview could not be loaded">
        {(data) => (
          <>
            <section aria-label="Security summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Open alerts" value={data.openAlerts} icon={ShieldAlert} tone="warning" description="Open or investigating events" />
              <StatCard label="Critical-risk agents" value={data.riskDistribution.critical} icon={ShieldX} tone="danger" />
              <StatCard label="High-risk agents" value={data.riskDistribution.high} icon={TriangleAlert} tone="warning" />
              <StatCard label="Checks passed" value={data.checks.passed} icon={ShieldCheck} tone="success" description={`${data.checks.failed} failed · ${data.checks.warning} warnings`} />
            </section>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <RiskDistributionCard overview={data} />
              <SecurityChecksCard overview={data} />
            </div>

            <Card className="mt-6">
              <CardHeader title="Permission overview" description="How many agents hold each capability, by access level." />
              <div className="p-4">
                <PermissionOverviewTable rows={data.permissions} />
              </div>
            </Card>
          </>
        )}
      </QueryState>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Recent security events" />
          <div className="p-4">
            <QueryState query={events} loading={<LoadingState variant="table" label="Loading security events…" />} errorTitle="Security events could not be loaded">
              {(rows) => <SecurityEventsTable events={rows} />}
            </QueryState>
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Alerts" description="Open high and critical events." />
            <div className="p-4">
              <QueryState query={events} loading={<LoadingState variant="inline" label="Loading alerts…" />} errorTitle="Alerts could not be loaded">
                {(rows) => <AlertsList events={rows} />}
              </QueryState>
            </div>
          </Card>

          <Card>
            <CardHeader title="Policy status" />
            <QueryState query={policies} loading={<LoadingState variant="inline" label="Loading policies…" className="p-4" />} errorTitle="Policies could not be loaded">
              {(rows) => <PolicyList policies={rows} />}
            </QueryState>
          </Card>
        </div>
      </div>
    </>
  );
}
