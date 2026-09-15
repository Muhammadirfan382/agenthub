import { useFormContext, useWatch } from 'react-hook-form';
import { RiskBadge } from '@/components/status/StatusBadges';
import { CATEGORY_LABELS, CAPABILITY_META } from '@/components/status/meta';
import { Badge } from '@/components/ui/Badge';
import { deriveRisk } from '@/lib/risk';
import { formatNumber } from '@/lib/format';
import type { AgentCategory } from '@/types/domain';
import { FormSection } from '../FormSection';
import { type AgentFormInput, MODEL_OPTIONS, TOOL_OPTIONS, permissionRisk } from '../schema';

export function ReviewSection({ step }: { step: number }) {
  const { control } = useFormContext<AgentFormInput>();
  const values = useWatch({ control }) as AgentFormInput;

  const granted = (values.permissions ?? []).filter((p) => p.level !== 'denied');
  const risk = deriveRisk(
    granted.map((p) => ({ ...p, risk: permissionRisk(p.capability, p.level) })),
  );
  const category = values.category ? CATEGORY_LABELS[values.category as AgentCategory] : undefined;

  const rows: [string, React.ReactNode][] = [
    ['Name', values.name || <em className="text-fg-subtle">Not set</em>],
    ['Version', values.version ? `v${values.version}` : <em className="text-fg-subtle">Not set</em>],
    ['Category', category ?? <em className="text-fg-subtle">Not set</em>],
    ['Tags', values.tags?.length ? values.tags.join(', ') : <em className="text-fg-subtle">None</em>],
    ['Model', MODEL_OPTIONS.find((m) => m.value === values.model?.model)?.label ?? '—'],
    ['Tools', values.tools?.length ? values.tools.map((id) => TOOL_OPTIONS.find((t) => t.id === id)?.label ?? id).join(', ') : 'None'],
    [
      'Capabilities',
      granted.length ? (
        <span className="flex flex-wrap gap-1">
          {granted.map((p) => (
            <Badge key={p.capability}>{CAPABILITY_META[p.capability].label}</Badge>
          ))}
        </span>
      ) : (
        'None (deny all)'
      ),
    ],
    ['Max runtime', values.resourceLimits ? `${formatNumber(Number(values.resourceLimits.maxRuntimeSeconds) || 0)} s` : '—'],
    ['Sandbox', values.securityPolicy?.sandbox === 'strict' ? 'Strict' : 'Standard'],
    ['Network egress', values.securityPolicy?.networkEgress === 'allow_list' ? 'Allow-list' : 'None'],
  ];

  return (
    <FormSection id="review" step={step} title="Review" description="Check the configuration before saving.">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface-muted px-4 py-3">
        <span className="text-sm text-fg-muted">Indicative risk</span>
        <RiskBadge level={risk.level} />
        <span className="text-sm text-fg-muted tabular-nums">Score {risk.score}/100</span>
        <span className="text-xs text-fg-subtle">Estimated in the browser; not a security assessment.</span>
      </div>
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-xs text-fg-subtle">{label}</dt>
            <dd className="mt-0.5 text-sm break-words text-fg">{value}</dd>
          </div>
        ))}
      </dl>
    </FormSection>
  );
}
